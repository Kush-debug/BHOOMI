"""
Document processing pipeline.

Failure policy (BHUMI_FORENSICS_SPEC §2 rule 1): every stage either produces a
result derived from the uploaded file, or raises. The document is marked FAILED
with the real error, which is shown to the officer. Nothing is substituted.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_PROCESS, CAN_READ_DOCUMENTS, require_roles
from app.core.errors import (
    NoExtractableFieldsError,
    ProcessingError,
    TranslationUnavailableError,
)
from app.models.document import Document, DocumentPage
from app.models.ocr import Claim, EvidenceRegion, OcrRun
from app.models.user import User
from app.models.validation import ValidationResult
from app.services.analysis_service import analysis_service
from app.services.audit_service import audit_service
from app.services.confidence_service import confidence_service
from app.services.extraction_service import extraction_service
from app.services.identity_resolver import identity_resolver, normalize_identifier
from app.services.investigation_service import investigation_service
from app.services.notification_service import notification_service
from app.services.ocr_service import ocr_service
from app.services.translation_service import translation_service
from app.services.validation_service import validation_service

router = APIRouter(prefix="/processing", tags=["Processing Pipeline"])


def _record_failure(db: Session, doc: Document, exc: ProcessingError, user_id: int) -> None:
    doc.status = "failed"
    doc.validation_status = "failed"
    doc.processing_error_code = exc.code
    doc.processing_error_message = exc.message
    doc.processing_failed_stage = getattr(exc, "stage", "unknown")
    db.commit()
    audit_service.log_event(
        db,
        action="PROCESSING_FAILED",
        user_id=user_id,
        document_id=doc.id,
        details={"code": exc.code, "stage": doc.processing_failed_stage, "message": exc.message},
    )


@router.post("/{id}/start")
def start_processing(
    id: int,
    target_language: str = Query("en", description="Translation target: en, hi, ta, te, kn, ..."),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_PROCESS)),
):
    """Run the pipeline over the ACTUAL uploaded file, every page.

    Stages: OCR (per page) -> language detection -> translation -> extraction ->
    confidence -> multi-tier validation.
    """
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    pages: List[DocumentPage] = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == doc.id)
        .order_by(DocumentPage.page_number.asc())
        .all()
    )
    if not pages:
        raise HTTPException(
            status_code=422,
            detail="This document has no rendered pages. Re-upload it so the pages can be rendered.",
        )

    doc.status = "processing"
    doc.processing_error_code = None
    doc.processing_error_message = None
    doc.processing_failed_stage = None
    db.commit()

    metadata = {
        "state": doc.state,
        "district": doc.district,
        "tehsil": doc.tehsil,
        "village": doc.village,
        "document_type": doc.document_type,
        "document_year": doc.document_year,
    }

    # ---- Stage: OCR every page -------------------------------------------
    page_results: List[Dict[str, Any]] = []
    try:
        for page in pages:
            image_path = page.preprocessed_image_path or page.original_image_path
            page_results.append(
                ocr_service.process_page(
                    image_path=image_path,
                    page_number=page.page_number,
                    lang_hint=doc.language,
                )
            )
    except ProcessingError as exc:
        _record_failure(db, doc, exc, current_user.id)
        raise HTTPException(status_code=exc.http_status, detail=exc.to_envelope()["error"])

    all_blocks: List[Dict[str, Any]] = []
    text_parts: List[str] = []
    conf_weighted = 0.0
    conf_words = 0
    for res in page_results:
        all_blocks.extend(res["blocks"])
        text_parts.append(f"[page {res['blocks'][0]['page_number'] if res['blocks'] else '?'}]\n{res['raw_text']}")
        if res["average_confidence"] is not None and res["word_count"]:
            conf_weighted += res["average_confidence"] * res["word_count"]
            conf_words += res["word_count"]

    combined_text = "\n\n".join(text_parts)
    page_mean_confidence = round(conf_weighted / conf_words, 4) if conf_words else None

    # Language: decide over the whole document, not page 1 alone.
    from app.services.language_detection_service import language_detection_service

    lang_res = language_detection_service.detect_language(combined_text, fallback_hint=doc.language or "en")

    doc.detected_language = lang_res["detected_language"]
    doc.detected_language_name = lang_res["language_name"]
    doc.language_confidence = lang_res["confidence"]
    doc.original_ocr_text = combined_text
    doc.ocr_confidence = page_mean_confidence
    doc.target_language = target_language

    # OcrRun is append-only (BHUMI_FORENSICS_SPEC §3.1): reprocessing never
    # deletes prior runs, it retires them (is_current=False) and adds new
    # ones. Every real OCR word this run produced is persisted as its own
    # EvidenceRegion row — not just the words that later matched an extracted
    # value — so the full OCR output stays queryable and auditable.
    db.query(OcrRun).filter(OcrRun.document_id == doc.id).update({"is_current": False})
    new_runs: List[OcrRun] = []
    for res in page_results:
        run = OcrRun(
            document_id=doc.id,
            page_number=res["blocks"][0]["page_number"] if res["blocks"] else 1,
            raw_text=res["raw_text"],
            layout_blocks=res["blocks"],
            detected_language=res["detected_language"],
            average_confidence=res["average_confidence"],
            engine_used=res["engine"],
            engine_version=res["engine_version"],
            engine_languages=res["engine_langs"],
            word_count=res["word_count"],
            page_width=res["page_width"],
            page_height=res["page_height"],
            status="SUCCEEDED",
            is_current=True,
        )
        db.add(run)
        new_runs.append(run)
    db.flush()  # assign ids so EvidenceRegion rows can reference ocr_run_id

    for run, res in zip(new_runs, page_results):
        for block in res["blocks"]:
            bbox = block.get("bbox")
            if not bbox:
                continue  # never persist a region without a real OCR-measured box
            db.add(
                EvidenceRegion(
                    ocr_run_id=run.id,
                    document_id=doc.id,
                    page_number=block.get("page_number", run.page_number),
                    text=block.get("text", ""),
                    bbox={"x": bbox[0], "y": bbox[1], "w": bbox[2], "h": bbox[3]}
                    if isinstance(bbox, (list, tuple))
                    else bbox,
                    page_width=run.page_width,
                    page_height=run.page_height,
                    ocr_confidence=block.get("confidence"),
                    geometry_source="OCR_WORD_BOX",
                    line_num=block.get("line_num"),
                    word_num=block.get("block_num"),
                )
            )
    db.flush()  # autoflush is off on this session — the claims query below needs these regions visible

    # ---- Stage: translation (non-fatal) ----------------------------------
    doc.translated_text = None
    doc.translation_confidence = None
    try:
        translated = translation_service.translate_text(
            combined_text, source_lang=doc.detected_language, target_lang=target_language
        )
        doc.translated_text = translated["text"]
        doc.translation_confidence = translated.get("confidence")
    except TranslationUnavailableError:
        pass  # original OCR is preserved; the UI shows translation as unavailable

    # ---- Stage: extraction ------------------------------------------------
    extracted = extraction_service.extract_structured_fields(
        raw_text=combined_text,
        ocr_blocks=all_blocks,
        metadata=metadata,
        detected_lang=doc.detected_language,
        page_mean_confidence=page_mean_confidence,
    )

    if not extraction_service.has_land_record_signal(extracted):
        exc = NoExtractableFieldsError(
            "OCR succeeded, but no land-record fields were found in this document. "
            "No owner, khasra/khata/survey number or area could be located in the text.",
            details={
                "characters_read": len(combined_text.strip()),
                "pages_processed": len(page_results),
                "detected_language": doc.detected_language,
                "text_preview": combined_text.strip()[:300],
                "next_steps": [
                    "confirm the file is a land record and not another document type",
                    "check the scan is legible and right side up",
                    "confirm a language pack for this script is installed",
                ],
            },
        )
        _record_failure(db, doc, exc, current_user.id)
        raise HTTPException(status_code=exc.http_status, detail=exc.to_envelope()["error"])

    enriched = translation_service.generate_multilingual_representations(
        extracted_fields=extracted,
        source_lang=doc.detected_language,
        target_lang=target_language,
    )

    # Claims are append-only (BHUMI_FORENSICS_SPEC §3.1): reprocessing never
    # deletes the previous claims — it supersedes them, so an officer's prior
    # correction and every past AI extraction stay in the audit trail. An
    # officer's own correction (asserted_by=OFFICER) is never silently
    # replaced by a re-run of the automated pipeline.
    prior_claims = (
        db.query(Claim)
        .filter(Claim.document_id == doc.id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )
    prior_by_field: Dict[str, Claim] = {c.standardized_field: c for c in prior_claims}
    officer_held_fields = {
        f for f, c in prior_by_field.items() if c.asserted_by == "OFFICER"
    }
    for c in prior_claims:
        if c.asserted_by != "OFFICER":
            c.lifecycle_status = "SUPERSEDED"

    # Look up the EvidenceRegion rows just written for this run so each claim
    # that matched real OCR words can point back to the one it came from —
    # the edge the /claims/{id}/evidence endpoint walks.
    current_regions = (
        db.query(EvidenceRegion)
        .join(OcrRun, EvidenceRegion.ocr_run_id == OcrRun.id)
        .filter(OcrRun.document_id == doc.id, OcrRun.is_current.is_(True))
        .all()
    )

    def _find_region(anchor: Dict[str, Any] | None) -> EvidenceRegion | None:
        if not anchor:
            return None
        for r in current_regions:
            if (
                r.page_number == anchor.get("page_number")
                and r.line_num == anchor.get("line_num")
                and r.word_num == anchor.get("block_num")
                and r.text == anchor.get("text")
            ):
                return r
        return None

    fields_dict: Dict[str, Any] = {}
    for ef in enriched:
        field_key = ef["standardized_field"]
        if field_key in officer_held_fields:
            # An officer already corrected this field on this document; the
            # automated re-extraction is recorded nowhere near their claim,
            # not even superseding it. Their value stays authoritative until
            # they change it themselves.
            fields_dict[field_key] = prior_by_field[field_key].field_value
            continue

        region = _find_region(ef.get("_evidence_anchor"))
        db.add(
            Claim(
                document_id=doc.id,
                field_name=ef["field_name"],
                standardized_field=field_key,
                field_value=ef["field_value"],
                original_value=ef.get("original_value"),
                translated_value=ef.get("translated_value"),
                transliteration=ef.get("transliteration"),
                translations_json=ef.get("translations_json", {}),
                confidence=ef.get("confidence"),
                confidence_basis=ef.get("confidence_basis"),
                confidence_breakdown=ef.get("confidence_breakdown", {}),
                source_text=ef.get("source_text"),
                page_number=ef.get("page_number"),
                bounding_box=ef.get("bounding_box"),
                bbox_source=ef.get("bbox_source", "NONE"),
                evidence_region_id=region.id if region else None,
                extraction_method="REGEX_RULE",
                provenance=ef.get("provenance", "DOCUMENT_OCR"),
                status=ef.get("status", "auto_extracted"),
                lifecycle_status="ACCEPTED",
                asserted_by="SYSTEM",
                supersedes_claim_id=(
                    prior_by_field[field_key].id if field_key in prior_by_field else None
                ),
            )
        )
        fields_dict[field_key] = ef["field_value"]

    # ---- Stage: identity resolution (Phase 3) -----------------------------
    #
    # Links this document's current claims to a durable Parcel (by khasra
    # number + location) and a durable Person (by owner/father name), so a
    # second document about the same khasra number converges on the same
    # parcel instead of staying an unrelated claim (BHUMI_FORENSICS_SPEC
    # §3.2). Never fatal: a document with no khasra number simply has
    # unresolved claims, which is honest, not an error.
    db.flush()  # autoflush is off — the resolver's alias lookups need the new claims' ids
    current_claims = (
        db.query(Claim)
        .filter(Claim.document_id == doc.id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )
    khasra_claim = next((c for c in current_claims if c.standardized_field == "khasra_number"), None)
    if khasra_claim and khasra_claim.field_value:
        resolution = identity_resolver.resolve_parcel(
            db,
            state=doc.state,
            district=doc.district,
            tehsil=doc.tehsil,
            village=doc.village,
            khasra_raw=khasra_claim.field_value,
        )
        if resolution:
            resolution.parcel.last_seen_year = doc.document_year
            if resolution.parcel.first_seen_year is None or (
                doc.document_year and doc.document_year < resolution.parcel.first_seen_year
            ):
                resolution.parcel.first_seen_year = doc.document_year
            khata_claim = next((c for c in current_claims if c.standardized_field == "khata_number"), None)
            if khata_claim and khata_claim.field_value and not resolution.parcel.khata_number_norm:
                resolution.parcel.khata_number_norm = normalize_identifier(khata_claim.field_value)
            for c in current_claims:
                c.parcel_id = resolution.parcel.id

    for field_key in ("owner_name", "father_name"):
        claim = next((c for c in current_claims if c.standardized_field == field_key), None)
        if claim and claim.field_value:
            person_res = identity_resolver.resolve_person(db, claim.field_value)
            if person_res:
                claim.person_id = person_res.person.id

    # ---- Stage: analysis (Phase 5) — events, matching, contradictions ----
    #
    # Regenerates LandEvents and Findings for the parcel this document
    # resolved to: an unexplained material transition becomes an EVIDENCE_GAP,
    # two documents disagreeing in one year become a CONTRADICTION. Never
    # fatal (matches RESOLVE): the document still finishes if analysis
    # errors, and findings an officer has already acted on are never touched.
    parcel_for_analysis = next((c.parcel_id for c in current_claims if c.parcel_id), None)
    if parcel_for_analysis:
        db.flush()
        try:
            analysis_service.analyze_parcel(db, parcel_for_analysis)
        except Exception as exc:  # noqa: BLE001 — analysis must never block processing
            audit_service.log_event(
                db,
                action="ANALYSIS_FAILED",
                user_id=current_user.id,
                document_id=doc.id,
                details={"parcel_id": parcel_for_analysis, "error": str(exc)},
            )

    # ---- Stage: scoring (Phase 6) — sufficiency, priority, investigation --
    #
    # Runs after ANALYSE so findings exist to score. Computes and persists
    # this parcel's EvidenceSufficiencyScore, sets Finding.evidence_sufficiency
    # on every active finding, scores each with PriorityScorer, and
    # opens/refreshes the parcel's InvestigationCase. Never fatal, same
    # pattern as RESOLVE/ANALYSE: a scoring error leaves prior scores/cases
    # untouched rather than blocking the document from finishing.
    if parcel_for_analysis:
        db.flush()
        try:
            investigation_service.score_and_prioritize_parcel(db, parcel_for_analysis)
        except Exception as exc:  # noqa: BLE001 — scoring must never block processing
            audit_service.log_event(
                db,
                action="SCORING_FAILED",
                user_id=current_user.id,
                document_id=doc.id,
                details={"parcel_id": parcel_for_analysis, "error": str(exc)},
            )

    # ---- Stage: confidence -----------------------------------------------
    conf_metrics = confidence_service.calculate_document_confidence(enriched)
    doc.extraction_confidence = conf_metrics["overall_confidence"]

    # ---- Stage: validation ------------------------------------------------
    db.query(ValidationResult).filter(ValidationResult.document_id == doc.id).delete()
    anomalies = validation_service.validate_extracted_data(db, doc, fields_dict)
    for anom in anomalies:
        db.add(
            ValidationResult(
                document_id=doc.id,
                validation_type=anom["validation_type"],
                rule_name=anom["rule_name"],
                severity=anom["severity"],
                status="failed",
                field_name=anom.get("field_name"),
                expected_value=anom.get("expected_value"),
                actual_value=anom.get("actual_value"),
                message=anom["message"],
            )
        )

    # validation_confidence is the share of executed rules that passed. It is a
    # measurement, not the 0.96 literal this endpoint used to assign.
    rules_run = validation_service.RULES_EXECUTED_PER_DOCUMENT
    doc.validation_confidence = round(max(0.0, (rules_run - len(anomalies)) / rules_run), 4)

    has_errors = any(a["severity"] == "error" for a in anomalies)
    needs_review = has_errors or conf_metrics["requires_human_verification"] or bool(anomalies)

    doc.status = "verification_pending" if needs_review else "processed"
    doc.validation_status = "failed" if has_errors else ("warning" if anomalies else "valid")

    db.commit()
    db.refresh(doc)

    audit_service.log_event(
        db,
        action="PROCESSING_COMPLETED",
        user_id=current_user.id,
        document_id=doc.id,
        details={
            "pages_processed": len(page_results),
            "ocr_engine": page_results[0]["engine"],
            "ocr_confidence": doc.ocr_confidence,
            "detected_language": doc.detected_language,
            "fields_extracted": len(enriched),
            "anomalies": len(anomalies),
            "status": doc.status,
        },
    )

    if needs_review:
        notification_service.send(
            db,
            title=f"Verification required: {doc.file_name}",
            message=f"{len(anomalies)} validation issue(s) on a {doc.detected_language_name} document.",
            user_id=current_user.id,
            notif_type="warning",
            link=f"/verification/{doc.id}",
        )

    return {
        "status": "success",
        "document_id": doc.id,
        "pipeline_state": doc.status,
        "pages_processed": len(page_results),
        "ocr_engine": page_results[0]["engine"],
        "ocr_engine_version": page_results[0]["engine_version"],
        "detected_language": doc.detected_language,
        "detected_language_name": doc.detected_language_name,
        "language_confidence": doc.language_confidence,
        "ocr_confidence": doc.ocr_confidence,
        "extraction_confidence": doc.extraction_confidence,
        "translation_confidence": doc.translation_confidence,
        "validation_confidence": doc.validation_confidence,
        "anomalies_found": len(anomalies),
        "fields_extracted": len(enriched),
        "fields_without_source_region": sum(
            1 for e in enriched if e.get("bbox_source", "NONE") == "NONE"
        ),
    }


@router.post("/{id}/translate")
def switch_translation_language(
    id: int,
    target_lang: str = Query("en"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_PROCESS)),
):
    """Re-translate stored OCR text and field values. Does not re-run OCR."""
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fields = (
        db.query(Claim)
        .filter(Claim.document_id == doc.id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )
    if not fields:
        raise HTTPException(status_code=400, detail="This document has not been processed yet.")

    try:
        full = translation_service.translate_text(
            doc.original_ocr_text or "",
            source_lang=doc.detected_language or "en",
            target_lang=target_lang,
        )
        doc.translated_text = full["text"]
        doc.translation_confidence = full.get("confidence")
    except TranslationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=exc.to_envelope()["error"])

    # Re-translating changes how a value is displayed, not what was extracted,
    # so it updates the current ACCEPTED claim in place rather than creating a
    # superseding one — unlike an officer's correction, which always does.
    for f in fields:
        if f.provenance == "OFFICER_CORRECTION":
            continue  # never re-translate over a human decision
        res = translation_service.translate_field(
            field_key=f.standardized_field,
            original_value=f.original_value or f.field_value,
            source_lang=doc.detected_language or "en",
            target_lang=target_lang,
        )
        f.translated_value = res["translated_value"]
        f.field_value = res["translations_json"].get(target_lang, res["original_value"])

    doc.target_language = target_lang
    db.commit()
    return {"status": "success", "document_id": doc.id, "target_language": target_lang, "fields_updated": len(fields)}


@router.get("/{id}/pipeline-status")
def get_pipeline_status(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    ocr_rows = (
        db.query(OcrRun)
        .filter(OcrRun.document_id == doc.id, OcrRun.is_current.is_(True))
        .all()
    )
    fields = (
        db.query(Claim)
        .filter(Claim.document_id == doc.id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )
    anomalies = db.query(ValidationResult).filter(ValidationResult.document_id == doc.id).all()

    def stage(done: bool, name: str, **extra):
        if doc.status == "failed" and doc.processing_failed_stage == extra.pop("_stage", None):
            return {"status": "failed", "name": name, "error": doc.processing_error_message, **extra}
        return {"status": "completed" if done else "pending", "name": name, **extra}

    return {
        "document_id": doc.id,
        "status": doc.status,
        "validation_status": doc.validation_status,
        "failure": (
            {
                "code": doc.processing_error_code,
                "stage": doc.processing_failed_stage,
                "message": doc.processing_error_message,
            }
            if doc.status == "failed"
            else None
        ),
        "detected_language": doc.detected_language,
        "detected_language_name": doc.detected_language_name,
        "confidence_scores": {
            "language_detection": doc.language_confidence,
            "ocr": doc.ocr_confidence,
            "field_extraction": doc.extraction_confidence,
            "translation": doc.translation_confidence,
            "validation": doc.validation_confidence,
        },
        "stages": {
            "file_validation": stage(True, "File & format verification"),
            "preprocessing": stage(bool(doc.pages), "OpenCV enhancement (CLAHE, denoise, threshold)"),
            "ocr": stage(
                bool(ocr_rows),
                "OCR",
                _stage="ocr",
                pages=len(ocr_rows),
                confidence=doc.ocr_confidence,
                engine=ocr_rows[0].engine_used if ocr_rows else None,
            ),
            "language_detection": stage(
                bool(ocr_rows), "Script & language detection", detected=doc.detected_language_name
            ),
            "translation": stage(
                bool(doc.translated_text), "Identifier-protected translation", target=doc.target_language
            ),
            "field_extraction": stage(
                bool(fields), "Field extraction", _stage="extract", fields_count=len(fields)
            ),
            "confidence_scoring": stage(bool(fields), "Confidence scoring"),
            "validation": stage(bool(ocr_rows), "Multi-tier validation", anomalies_count=len(anomalies)),
        },
    }


@router.get("/engine-status")
def engine_status(current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS))):
    """What the OCR stack can actually do on this server, right now."""
    return ocr_service.engine_status()
