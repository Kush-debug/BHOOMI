"""
The evidence graph's read API (BHUMI_FORENSICS_SPEC.md §6).

Every fact a screen shows is a `Claim`; every `Claim` can be walked back to
the `EvidenceRegion`, `OcrRun`, `DocumentPage` and `Document` that produced
it. These three endpoints are that walk, exposed directly, so "why does the
system believe this?" is a query instead of a promise:

  GET /documents/{id}/claims    current claims for a document (+ full history
                                 on request), each showing what it supersedes
  GET /documents/{id}/regions   every OCR word region persisted for a
                                 document — the full OCR output, not just the
                                 words that happened to match a claim
  GET /claims/{id}/evidence     one claim's complete provenance chain
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_READ_DOCUMENTS, require_roles
from app.models.document import Document
from app.models.ocr import Claim, EvidenceRegion, OcrRun
from app.models.user import User

router = APIRouter(tags=["Evidence"])


def _claim_dict(c: Claim) -> Dict[str, Any]:
    return {
        "id": c.id,
        "document_id": c.document_id,
        "field_name": c.field_name,
        "standardized_field": c.standardized_field,
        "field_value": c.field_value,
        "confidence": c.confidence,
        "confidence_basis": c.confidence_basis,
        "source_text": c.source_text,
        "page_number": c.page_number,
        "bounding_box": c.bounding_box,
        "bbox_source": c.bbox_source,
        "evidence_region_id": c.evidence_region_id,
        "provenance": c.provenance,
        "status": c.status,
        "lifecycle_status": c.lifecycle_status,
        "asserted_by": c.asserted_by,
        "officer_id": c.officer_id,
        "supersedes_claim_id": c.supersedes_claim_id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _region_dict(r: EvidenceRegion) -> Dict[str, Any]:
    return {
        "id": r.id,
        "ocr_run_id": r.ocr_run_id,
        "document_id": r.document_id,
        "page_number": r.page_number,
        "text": r.text,
        "bbox": r.bbox,
        "page_width": r.page_width,
        "page_height": r.page_height,
        "ocr_confidence": r.ocr_confidence,
        "geometry_source": r.geometry_source,
    }


@router.get("/documents/{id}/claims")
def get_document_claims(
    id: int,
    include_superseded: bool = Query(False, description="Include SUPERSEDED and REJECTED claims, not just the current ACCEPTED ones"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    q = db.query(Claim).filter(Claim.document_id == id)
    if not include_superseded:
        q = q.filter(Claim.lifecycle_status == "ACCEPTED")
    claims = q.order_by(Claim.standardized_field, Claim.created_at.desc()).all()

    return {
        "document_id": id,
        "include_superseded": include_superseded,
        "count": len(claims),
        "claims": [_claim_dict(c) for c in claims],
    }


@router.get("/documents/{id}/regions")
def get_document_regions(
    id: int,
    page: Optional[int] = Query(None, description="Restrict to one page number"),
    current_only: bool = Query(True, description="Only regions from the current OCR run per page (set false to include retired reprocessing runs)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    q = db.query(EvidenceRegion).filter(EvidenceRegion.document_id == id)
    if current_only:
        q = q.join(OcrRun, EvidenceRegion.ocr_run_id == OcrRun.id).filter(OcrRun.is_current.is_(True))
    if page is not None:
        q = q.filter(EvidenceRegion.page_number == page)
    regions = q.order_by(EvidenceRegion.page_number, EvidenceRegion.id).all()

    return {
        "document_id": id,
        "current_only": current_only,
        "count": len(regions),
        "regions": [_region_dict(r) for r in regions],
    }


@router.get("/claims/{id}/evidence")
def get_claim_evidence(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    """The 'why does the system believe this?' endpoint.

    Walks Claim -> EvidenceRegion -> OcrRun -> DocumentPage -> Document, and
    also returns the supersession chain in both directions so an officer can
    see exactly what this claim replaced and (if applicable) what replaced it.
    """
    claim = db.query(Claim).filter(Claim.id == id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    doc = db.query(Document).filter(Document.id == claim.document_id).first()

    region: Optional[EvidenceRegion] = None
    ocr_run: Optional[OcrRun] = None
    if claim.evidence_region_id:
        region = db.query(EvidenceRegion).filter(EvidenceRegion.id == claim.evidence_region_id).first()
        if region:
            ocr_run = db.query(OcrRun).filter(OcrRun.id == region.ocr_run_id).first()

    superseded_claim = (
        db.query(Claim).filter(Claim.id == claim.supersedes_claim_id).first()
        if claim.supersedes_claim_id
        else None
    )
    superseded_by = (
        db.query(Claim)
        .filter(Claim.supersedes_claim_id == claim.id)
        .order_by(Claim.created_at.desc())
        .first()
    )

    return {
        "claim": _claim_dict(claim),
        "evidence_region": _region_dict(region) if region else None,
        "evidence_available": region is not None,
        "no_evidence_reason": (
            None
            if region is not None
            else (
                "supplied on the upload form, not extracted from the document"
                if claim.provenance == "UPLOAD_METADATA"
                else "an officer entered this value directly"
                if claim.provenance == "OFFICER_CORRECTION"
                else "this value could not be matched to specific OCR words on the page"
            )
        ),
        "ocr_run": (
            {
                "id": ocr_run.id,
                "engine": ocr_run.engine_used,
                "engine_version": ocr_run.engine_version,
                "page_number": ocr_run.page_number,
                "mean_word_confidence": ocr_run.average_confidence,
                "created_at": ocr_run.created_at.isoformat() if ocr_run.created_at else None,
            }
            if ocr_run
            else None
        ),
        "document": (
            {
                "id": doc.id,
                "file_name": doc.file_name,
                "source_class": doc.source_class,
            }
            if doc
            else None
        ),
        "supersedes": _claim_dict(superseded_claim) if superseded_claim else None,
        "superseded_by": _claim_dict(superseded_by) if superseded_by else None,
    }
