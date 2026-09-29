"""
Findings API (BHUMI_FORENSICS_SPEC.md §6 — Phase 5 read, Phase 7 resolve).

A Finding is an investigation signal — a material change with no supporting
event, or two documents that disagree — not a verdict.

  GET  /findings?type=&severity=&status=&parcel_id=
  GET  /findings/{id}
  POST /findings/{id}/resolve   -- Phase 7: an officer moves it off OPEN

Once a finding is resolved here, `analysis_service`'s reconciliation
(Phase 5) already refuses to touch it on reprocessing —
`Finding.is_officer_owned` covers exactly the states this endpoint can set.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_READ_FINDINGS, CAN_RESOLVE_FINDINGS, require_roles
from app.models.document import Document
from app.models.finding import RES_DISMISSED, RES_RESOLVED, Finding
from app.models.parcel import Parcel
from app.models.user import User
from app.schemas.investigation import ResolveFindingRequest
from app.services.audit_service import audit_service

router = APIRouter(prefix="/findings", tags=["Findings"])


def _render_explanation(f: Finding) -> str:
    try:
        return f.explanation_template.format(**(f.explanation_params_json or {}))
    except (KeyError, IndexError, ValueError):
        return f.explanation_template


def _finding_dict(f: Finding) -> Dict[str, Any]:
    return {
        "id": f.id,
        "finding_type": f.finding_type,
        "parcel_id": f.parcel_id,
        "severity": f.severity,
        "affected_predicates": f.affected_predicates or [],
        "time_range": {"start": f.time_range_start, "end": f.time_range_end},
        "source_claim_ids": f.source_claim_ids or [],
        "source_document_ids": f.source_document_ids or [],
        "rule_id": f.rule_id,
        "rule_version": f.rule_version,
        "explanation": _render_explanation(f),
        "explanation_template": f.explanation_template,
        "explanation_params": f.explanation_params_json or {},
        "evidence_sufficiency": f.evidence_sufficiency,  # NULL until Phase 6
        "recommended_action": f.recommended_action,
        "resolution_status": f.resolution_status,
        "resolved_by": f.resolved_by,
        "resolution_note": f.resolution_note,
        "engine_version": f.engine_version,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


@router.get("")
def list_findings(
    type: Optional[str] = Query(None, description="CONTRADICTION | EVIDENCE_GAP | ..."),
    severity: Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    status: Optional[str] = Query(None, description="OPEN | IN_REVIEW | RESOLVED | DISMISSED"),
    parcel_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    q = db.query(Finding)
    if type:
        q = q.filter(Finding.finding_type == type.upper())
    if severity:
        q = q.filter(Finding.severity == severity.upper())
    if status:
        q = q.filter(Finding.resolution_status == status.upper())
    if parcel_id is not None:
        q = q.filter(Finding.parcel_id == parcel_id)

    total = q.count()
    _severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    rows = q.all()
    rows.sort(key=lambda f: (_severity_order.get(f.severity, 9), -(f.id or 0)))
    rows = rows[offset : offset + limit]

    return {"total": total, "count": len(rows), "findings": [_finding_dict(f) for f in rows]}


@router.get("/{finding_id}")
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    f = db.query(Finding).filter(Finding.id == finding_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    parcel = db.query(Parcel).filter(Parcel.id == f.parcel_id).first()
    docs = (
        db.query(Document).filter(Document.id.in_(f.source_document_ids or [])).all()
        if f.source_document_ids
        else []
    )
    out = _finding_dict(f)
    out["parcel"] = (
        {
            "id": parcel.id,
            "khasra_number": parcel.khasra_number_norm,
            "village": parcel.village,
            "tehsil": parcel.tehsil,
            "district": parcel.district,
            "state": parcel.state,
        }
        if parcel
        else None
    )
    out["source_documents"] = [
        {"id": d.id, "file_name": d.file_name, "source_class": d.source_class, "document_year": d.document_year}
        for d in docs
    ]
    return out


@router.post("/{finding_id}/resolve")
def resolve_finding(
    finding_id: int,
    body: ResolveFindingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_RESOLVE_FINDINGS)),
):
    """
    Phase 7: an officer moves a finding off OPEN. IN_REVIEW just marks it as
    being worked; RESOLVED/DISMISSED require a note explaining why (a bare
    status flip with no reasoning isn't an audit trail, it's a checkbox).

    Once this returns, `Finding.is_officer_owned` is true and
    `analysis_service`'s reconciliation (Phase 5) will never touch this row
    again on reprocessing — this endpoint is the only way a finding leaves
    the system-owned state.
    """
    f = db.query(Finding).filter(Finding.id == finding_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")

    if f.resolution_status in (RES_RESOLVED, RES_DISMISSED):
        raise HTTPException(
            status_code=409,
            detail=f"Finding is already {f.resolution_status}; this endpoint does not reopen findings.",
        )

    if body.resolution_status in (RES_RESOLVED, RES_DISMISSED) and not (body.resolution_note or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A resolution_note is required when resolving or dismissing a finding.",
        )

    previous_status = f.resolution_status
    f.resolution_status = body.resolution_status
    f.resolved_by = current_user.id
    if body.resolution_note:
        f.resolution_note = body.resolution_note

    audit_service.log_event(
        db,
        action="FINDING_RESOLVED",
        user_id=current_user.id,
        document_id=(f.source_document_ids or [None])[0],
        details={
            "finding_id": f.id,
            "parcel_id": f.parcel_id,
            "finding_type": f.finding_type,
            "previous_status": previous_status,
            "new_status": f.resolution_status,
            "resolution_note": f.resolution_note,
        },
    )
    db.commit()

    return _finding_dict(f)
