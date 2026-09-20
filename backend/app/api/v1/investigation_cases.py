"""
Investigation case API (BHUMI_FORENSICS_SPEC.md §3.3 / §5.9 — Phase 6 read,
Phase 7 workflow).

The prioritised queue: one row per parcel with active findings, ordered by
`priority_score`.

  GET  /investigation-cases?status=&band=&parcel_id=
  GET  /investigation-cases/{id}
  POST /investigation-cases/{id}/assign    -- Phase 7
  POST /investigation-cases/{id}/comment   -- Phase 7
  POST /investigation-cases/{id}/resolve   -- Phase 7

Every write here also marks the case officer-owned
(`InvestigationCase.is_officer_owned`), which is what stops
`investigation_service`'s regeneration (Phase 6) from touching
`assigned_to`/`status`/`comments`/`resolution` on the next SCORE run — see
that module's docstring for the reconciliation rule this relies on.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_MANAGE_INVESTIGATIONS, CAN_READ_FINDINGS, STAFF_ROLES, require_roles
from app.models.finding import Finding
from app.models.investigation import STATUS_CLOSED, STATUS_IN_PROGRESS, STATUS_OPEN, InvestigationCase
from app.models.parcel import Parcel
from app.models.user import User
from app.schemas.investigation import AssignCaseRequest, CommentCaseRequest, ResolveCaseRequest
from app.services.audit_service import audit_service

router = APIRouter(prefix="/investigation-cases", tags=["Investigation"])


def _case_dict(c: InvestigationCase, parcel: Optional[Parcel] = None) -> Dict[str, Any]:
    out = {
        "id": c.id,
        "parcel_id": c.parcel_id,
        "finding_ids": c.finding_ids or [],
        "priority_score": c.priority_score,
        "priority_band": c.priority_band,
        "priority_breakdown": c.priority_breakdown_json or {},
        "assigned_to": c.assigned_to,
        "status": c.status,
        "opened_at": c.opened_at.isoformat() if c.opened_at else None,
        "sla_due_at": c.sla_due_at.isoformat() if c.sla_due_at else None,
        "comments": c.comments or [],
        "resolution": c.resolution,
        "engine_version": c.engine_version,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }
    if parcel is not None:
        out["parcel"] = {
            "id": parcel.id,
            "khasra_number": parcel.khasra_number_norm,
            "village": parcel.village,
            "tehsil": parcel.tehsil,
            "district": parcel.district,
            "state": parcel.state,
        }
    return out


@router.get("")
def list_cases(
    status: Optional[str] = Query(None, description="OPEN | IN_PROGRESS | CLOSED"),
    band: Optional[str] = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    parcel_id: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    q = db.query(InvestigationCase)
    if status:
        q = q.filter(InvestigationCase.status == status.upper())
    if band:
        q = q.filter(InvestigationCase.priority_band == band.upper())
    if parcel_id is not None:
        q = q.filter(InvestigationCase.parcel_id == parcel_id)

    total = q.count()
    rows = q.all()
    # None-priority cases (every PriorityScorer term was unavailable) sort
    # last rather than crashing the comparison or silently ranking first.
    rows.sort(key=lambda c: (c.priority_score if c.priority_score is not None else -1.0), reverse=True)
    rows = rows[offset : offset + limit]

    return {"total": total, "count": len(rows), "cases": [_case_dict(c) for c in rows]}


@router.get("/{case_id}")
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    case = db.query(InvestigationCase).filter(InvestigationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Investigation case not found")

    parcel = db.query(Parcel).filter(Parcel.id == case.parcel_id).first()
    findings = (
        db.query(Finding).filter(Finding.id.in_(case.finding_ids or [])).all()
        if case.finding_ids
        else []
    )
    out = _case_dict(case, parcel)
    out["findings"] = [
        {
            "id": f.id,
            "finding_type": f.finding_type,
            "severity": f.severity,
            "resolution_status": f.resolution_status,
            "evidence_sufficiency": f.evidence_sufficiency,
            "explanation": (
                f.explanation_template.format(**(f.explanation_params_json or {}))
                if f.explanation_params_json
                else f.explanation_template
            ),
        }
        for f in findings
    ]
    return out


def _get_case_or_404(db: Session, case_id: int) -> InvestigationCase:
    case = db.query(InvestigationCase).filter(InvestigationCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Investigation case not found")
    return case


@router.post("/{case_id}/assign")
def assign_case(
    case_id: int,
    body: AssignCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_MANAGE_INVESTIGATIONS)),
):
    """Assign a case to an officer. If it's still OPEN, assignment moves it to
    IN_PROGRESS — picking up a case is what starts the investigation."""
    case = _get_case_or_404(db, case_id)
    if case.status == STATUS_CLOSED:
        raise HTTPException(status_code=409, detail="Case is CLOSED; reopen it before reassigning.")

    assignee = db.query(User).filter(User.id == body.assigned_to).first()
    if not assignee:
        raise HTTPException(status_code=404, detail=f"User {body.assigned_to} not found")
    if not assignee.is_active or assignee.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"User {body.assigned_to} is not an active staff member and cannot be assigned a case.",
        )

    previous_assignee = case.assigned_to
    case.assigned_to = assignee.id
    if case.status == STATUS_OPEN:
        case.status = STATUS_IN_PROGRESS

    audit_service.log_event(
        db,
        action="INVESTIGATION_CASE_ASSIGNED",
        user_id=current_user.id,
        details={
            "case_id": case.id,
            "parcel_id": case.parcel_id,
            "previous_assignee": previous_assignee,
            "new_assignee": assignee.id,
        },
    )
    db.commit()
    return _case_dict(case)


@router.post("/{case_id}/comment")
def comment_on_case(
    case_id: int,
    body: CommentCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_MANAGE_INVESTIGATIONS)),
):
    """Append a comment. Comments are additive and never edited/removed here —
    a full audit trail (spec §3.3/§14) means the record of who said what stays intact."""
    case = _get_case_or_404(db, case_id)

    comment = {
        "author_id": current_user.id,
        "author_name": current_user.full_name,
        "text": body.text,
        "created_at": datetime.utcnow().isoformat(),
    }
    # comments is a JSON column - reassign rather than .append() so SQLAlchemy
    # reliably detects the mutation (in-place mutation of a JSON-typed
    # attribute is not tracked without an explicit flag/event).
    case.comments = [*(case.comments or []), comment]

    audit_service.log_event(
        db,
        action="INVESTIGATION_CASE_COMMENTED",
        user_id=current_user.id,
        details={"case_id": case.id, "parcel_id": case.parcel_id, "comment": body.text},
    )
    db.commit()
    return _case_dict(case)


@router.post("/{case_id}/resolve")
def resolve_case(
    case_id: int,
    body: ResolveCaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_MANAGE_INVESTIGATIONS)),
):
    """
    Close a case. Deliberately independent of its findings' own
    `resolution_status` (see `investigation_service.py`'s docstring): closing
    the case here is the explicit officer action that Phase 6 said would
    exist but did not build. It does not resolve/dismiss the case's
    findings for you - do that via `POST /findings/{id}/resolve` first if
    that's the intent, so each finding's own resolution reason is recorded
    on the finding, not inferred from the case being closed.
    """
    case = _get_case_or_404(db, case_id)
    if case.status == STATUS_CLOSED:
        raise HTTPException(status_code=409, detail="Case is already CLOSED.")

    still_active = (
        db.query(Finding)
        .filter(Finding.id.in_(case.finding_ids or []), Finding.resolution_status.in_(("OPEN", "IN_REVIEW")))
        .count()
    )

    case.status = STATUS_CLOSED
    case.resolution = body.resolution

    audit_service.log_event(
        db,
        action="INVESTIGATION_CASE_RESOLVED",
        user_id=current_user.id,
        details={
            "case_id": case.id,
            "parcel_id": case.parcel_id,
            "resolution": body.resolution,
            "findings_still_active_at_close": still_active,
        },
    )
    db.commit()

    out = _case_dict(case)
    if still_active:
        # Not an error - an officer can legitimately close a case with
        # findings still open (e.g. escalated elsewhere) - but the response
        # says so plainly rather than silently hiding it.
        out["warning"] = f"{still_active} finding(s) linked to this case are still OPEN/IN_REVIEW."
    return out
