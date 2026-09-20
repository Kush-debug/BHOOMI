from datetime import datetime, date
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_APPROVE_RECORD, CAN_VERIFY, require_roles
from app.models.user import User
from app.models.document import Document
from app.models.ocr import Claim
from app.models.record import LandRecord
from app.models.validation import ValidationResult
from app.models.gis import GISParcel
from app.models.training import VerificationRecord
from app.schemas.record import VerificationSubmission, LandRecordResponse
from app.schemas.investigation import CorrectClaimRequest
from app.services.learning_service import learning_service
from app.services.audit_service import audit_service
from app.services.notification_service import notification_service

router = APIRouter(prefix="/verification", tags=["Human-in-the-Loop Verification"])


def _supersede_claim(
    db: Session,
    doc: Document,
    old_claim: Claim,
    field_key: str,
    new_val: Any,
    current_user: User,
    notes: Optional[str],
) -> Optional[Claim]:
    """
    One claim's correction, as a superseding claim (BHUMI_FORENSICS_SPEC §2
    rule 4 / §3.1) — the old claim is never edited in place, it's frozen as
    SUPERSEDED and a new claim is written with asserted_by=OFFICER, so both
    remain queryable and a correction is never mistaken for AI output.

    Extracted out of `submit_verification`'s per-field loop (Phase 2) so
    Phase 7's standalone per-claim endpoint can do exactly the same thing
    without a second, slightly-different copy of this logic. Behaviour for
    the existing `/submit` path is unchanged - this is the same code that
    was inline before, just callable from two places. Returns None (no-op)
    when the new value is identical to the old one.
    """
    orig_val = old_claim.field_value
    if orig_val == str(new_val):
        return None

    old_claim.lifecycle_status = "SUPERSEDED"

    new_claim = Claim(
        document_id=doc.id,
        # Carry the Phase 3 identity-resolution links forward. Without this
        # the superseding claim is parcel_id/person_id = NULL until the next
        # reprocess re-runs IdentityResolver, which means a just-corrected
        # value briefly disappears from the Phase 4 timeline, Phase 5
        # findings and Phase 6 sufficiency scoring - all of which query by
        # parcel_id. The claim itself is never wrong, only temporarily
        # invisible to parcel-scoped views; this closes that window.
        parcel_id=old_claim.parcel_id,
        person_id=old_claim.person_id,
        field_name=old_claim.field_name,
        standardized_field=field_key,
        field_value=str(new_val),
        original_value=old_claim.original_value,
        page_number=old_claim.page_number,
        source_text=old_claim.source_text,
        # The region an officer is correcting is still where the value lives
        # on the page; only the transcribed text and its confidence become
        # the officer's, not the geometry.
        bounding_box=old_claim.bounding_box,
        bbox_source=old_claim.bbox_source,
        evidence_region_id=old_claim.evidence_region_id,
        extraction_method="MANUAL",
        status="edited",
        provenance="OFFICER_CORRECTION",
        confidence=None,
        confidence_basis=f"entered by {current_user.username} during verification",
        lifecycle_status="ACCEPTED",
        asserted_by="OFFICER",
        officer_id=current_user.id,
        supersedes_claim_id=old_claim.id,
    )
    db.add(new_claim)

    learning_service.record_correction(
        db,
        document_id=doc.id,
        field_name=field_key,
        original_val=orig_val,
        corrected_val=str(new_val),
        verifier_id=current_user.id,
        doc_type=doc.document_type,
        language=doc.language,
        bounding_box=old_claim.bounding_box,
        notes=notes,
    )
    return new_claim

@router.get("/queue")
def get_verification_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_VERIFY)),
):
    """Returns all documents awaiting human verification with confidence and anomaly details."""
    docs = db.query(Document).filter(
        Document.status.in_(["verification_pending", "processing", "uploaded"])
    ).order_by(Document.created_at.desc()).all()

    queue_items = []
    for d in docs:
        anomalies = db.query(ValidationResult).filter(ValidationResult.document_id == d.id).all()
        queue_items.append({
            "id": d.id,
            "file_name": d.file_name,
            "document_type": d.document_type,
            "state": d.state,
            "district": d.district,
            "tehsil": d.tehsil,
            "village": d.village,
            "ocr_confidence": d.ocr_confidence,
            "extraction_confidence": d.extraction_confidence,
            "validation_status": d.validation_status,
            "anomalies_count": len(anomalies),
            "anomalies": [
                {"rule": a.rule_name, "severity": a.severity, "message": a.message} for a in anomalies
            ],
            "created_at": d.created_at
        })

    return queue_items

@router.post("/{doc_id}/submit")
def submit_verification(
    doc_id: int,
    submission: VerificationSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_APPROVE_RECORD)),
):
    """
    Submits human verification action:
    1. If approved or edited_approved:
       - Updates or creates verified `LandRecord`
       - Stores `TrainingCorrection` for any modified fields
       - Marks Validation anomalies as resolved
       - Updates GIS parcel status to 'verified'
       - Sets document status to 'verified'
    2. If rejected:
       - Sets document status to 'rejected'
    3. Logs immutable event to Audit Trail
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    extracted_fields = (
        db.query(Claim)
        .filter(Claim.document_id == doc.id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )
    fields_map = {f.standardized_field: f for f in extracted_fields}
    corrected_data = submission.corrected_fields or {}

    previous_state = {f.standardized_field: f.field_value for f in extracted_fields}
    # What the record would look like if every corrected field is applied —
    # computed in-memory only, nothing written to a claim yet. Validating
    # this BEFORE any claim is superseded (below) means a rejected approval
    # never leaves a partially-applied correction behind: a 422 from this
    # endpoint now genuinely means nothing was saved, matching what the
    # response implies and what "full audit" (Phase 7) requires — the old
    # order let `_supersede_claim` commit a correction, then raise 422 for
    # an unrelated missing field, with no VerificationRecord/audit entry for
    # the correction that had already landed.
    new_state = dict(previous_state)
    for field_key, new_val in corrected_data.items():
        if field_key in fields_map:
            new_state[field_key] = str(new_val)

    if submission.action in ["approved", "edited_approved"]:
        # These four values used to fall back to literals ("456", "142",
        # "राम प्रसाद", 0.0) when extraction found nothing, which wrote fabricated
        # data into the authoritative registry through the approval path
        # (ARCHITECTURE_AUDIT §4.7). An approval with missing mandatory fields is
        # now rejected and the officer is told exactly what to fill in — before
        # any claim is touched, so rejecting it is a true no-op.
        missing = [
            key
            for key in ("owner_name", "khasra_number", "khata_number", "area")
            if not str(new_state.get(key) or "").strip()
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "MISSING_MANDATORY_FIELDS",
                    "message": (
                        "This record cannot be approved: mandatory fields are missing. "
                        "Enter them in the workspace, or reject the document."
                    ),
                    "details": {"missing_fields": missing},
                },
            )

        try:
            area_val = float(str(new_state["area"]).strip())
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_AREA",
                    "message": f"Area '{new_state.get('area')}' is not a number. Correct it before approving.",
                    "details": {"field": "area"},
                },
            )
        if area_val <= 0:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_AREA",
                    "message": "Area must be greater than zero.",
                    "details": {"field": "area", "value": area_val},
                },
            )

        khasra_no = str(new_state["khasra_number"]).strip()
        khata_no = str(new_state["khata_number"]).strip()
        owner_str = str(new_state["owner_name"]).strip()

    # Validation (if any, above) passed — only now actually apply the
    # corrections, via the shared supersession helper (see
    # _supersede_claim's docstring). For "rejected"/"reprocessing_requested"
    # there's nothing to validate, so this runs unconditionally, same as before.
    corrections_logged = 0
    for field_key, new_val in corrected_data.items():
        if field_key in fields_map:
            old_claim = fields_map[field_key]
            new_claim = _supersede_claim(db, doc, old_claim, field_key, new_val, current_user, submission.notes)
            if new_claim is not None:
                fields_map[field_key] = new_claim
                corrections_logged += 1

    if submission.action in ["approved", "edited_approved"]:
        # Resolve anomalies
        anomalies = db.query(ValidationResult).filter(ValidationResult.document_id == doc.id).all()
        for a in anomalies:
            a.status = "resolved"

        # Create or update the verified LandRecord.
        existing_record = db.query(LandRecord).filter(LandRecord.document_id == doc.id).first()
        if not existing_record:
            existing_record = LandRecord(
                document_id=doc.id,
                state=str(new_state.get("state", doc.state)),
                district=str(new_state.get("district", doc.district)),
                tehsil=str(new_state.get("tehsil", doc.tehsil)),
                village=str(new_state.get("village", doc.village)),
                owner_name=owner_str,
                father_name=str(new_state.get("father_name", "")),
                khasra_number=khasra_no,
                khata_number=khata_no,
                area=area_val,
                area_unit=str(new_state.get("area_unit", "hectare")),
                land_classification=str(new_state.get("land_classification", "Agricultural")),
                mutation_number=str(new_state.get("mutation_number", "")),
                registration_number=str(new_state.get("registration_number", "")),
                verification_status="verified",
                verified_by=current_user.id,
                verified_at=datetime.utcnow(),
                verification_notes=submission.notes
            )
            db.add(existing_record)
        else:
            existing_record.owner_name = owner_str
            existing_record.father_name = str(new_state.get("father_name", ""))
            existing_record.khasra_number = khasra_no
            existing_record.khata_number = khata_no
            existing_record.area = area_val
            existing_record.verification_status = "verified"
            existing_record.verified_by = current_user.id
            existing_record.verified_at = datetime.utcnow()
            existing_record.verification_notes = submission.notes

        # Sync GIS Parcel status if matching parcel exists
        parcel = db.query(GISParcel).filter(
            GISParcel.khasra_number == khasra_no,
            GISParcel.village == doc.village
        ).first()
        if parcel:
            parcel.verification_status = "verified"
            parcel.owner_name = owner_str
            parcel.area = area_val

        doc.status = "verified"
        doc.validation_status = "verified"

    elif submission.action == "rejected":
        doc.status = "rejected"
        doc.validation_status = "failed"
    elif submission.action == "reprocessing_requested":
        doc.status = "uploaded"
        doc.validation_status = "pending"

    # Log verification record
    v_rec = VerificationRecord(
        document_id=doc.id,
        record_id=doc.land_record.id if doc.land_record else None,
        verifier_id=current_user.id,
        action=submission.action,
        previous_state=previous_state,
        new_state=new_state,
        notes=submission.notes
    )
    db.add(v_rec)
    db.commit()

    # Log Audit Event
    audit_service.log_event(
        db,
        action=f"DOCUMENT_VERIFICATION_{submission.action.upper()}",
        user_id=current_user.id,
        document_id=doc.id,
        details={
            "action": submission.action,
            "corrections_count": corrections_logged,
            "notes": submission.notes,
            "verifier": current_user.full_name
        }
    )

    return {
        "status": "success",
        "action": submission.action,
        "document_id": doc.id,
        "corrections_logged": corrections_logged,
        "message": "Verification recorded."
    }


@router.post("/{doc_id}/claims/{claim_id}/correct")
def correct_claim(
    doc_id: int,
    claim_id: int,
    body: CorrectClaimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_APPROVE_RECORD)),
):
    """
    Phase 7: evidence-linked verification, one field at a time
    (BHUMI_FORENSICS_SPEC.md §6 — `POST /verification/{doc_id}/claims/{claim_id}/correct`).

    Pairs with `GET /claims/{id}/evidence` (Phase 2): an officer looks at the
    highlighted OCR region behind a claim, decides it's wrong, and fixes just
    that field without having to submit the whole document through
    `/submit`. Same superseding-claim mechanics as `/submit` - see
    `_supersede_claim` - just reachable per-field instead of only as part of
    a full approve/reject decision.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    old_claim = (
        db.query(Claim)
        .filter(Claim.id == claim_id, Claim.document_id == doc_id, Claim.lifecycle_status == "ACCEPTED")
        .first()
    )
    if not old_claim:
        raise HTTPException(
            status_code=404,
            detail="No currently-accepted claim with this id on this document "
                   "(it may already have been superseded - corrections apply to current claims only).",
        )

    new_claim = _supersede_claim(
        db, doc, old_claim, old_claim.standardized_field, body.new_value, current_user, body.notes
    )
    if new_claim is None:
        return {
            "status": "unchanged",
            "message": "The submitted value is identical to the current claim; nothing was superseded.",
            "claim_id": old_claim.id,
        }

    db.commit()
    db.refresh(new_claim)

    audit_service.log_event(
        db,
        action="CLAIM_CORRECTED",
        user_id=current_user.id,
        document_id=doc.id,
        details={
            "field": old_claim.standardized_field,
            "superseded_claim_id": old_claim.id,
            "new_claim_id": new_claim.id,
            "old_value": old_claim.field_value,
            "new_value": new_claim.field_value,
            "notes": body.notes,
        },
    )

    return {
        "status": "success",
        "document_id": doc.id,
        "superseded_claim_id": old_claim.id,
        "new_claim": {
            "id": new_claim.id,
            "standardized_field": new_claim.standardized_field,
            "field_value": new_claim.field_value,
            "asserted_by": new_claim.asserted_by,
            "provenance": new_claim.provenance,
            "supersedes_claim_id": new_claim.supersedes_claim_id,
            "evidence_region_id": new_claim.evidence_region_id,
        },
        "message": "Claim corrected. The original claim is preserved as SUPERSEDED, not deleted.",
    }
