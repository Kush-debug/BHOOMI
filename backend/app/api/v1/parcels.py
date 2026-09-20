"""
Parcel search and detail (BHUMI_FORENSICS_SPEC.md §6, §9 Phase 3 gate).

The Phase 3 gate is exactly what this router proves: "two documents about one
Khasra converge on one parcel" — `GET /parcels/{key}` returns every document
and claim linked to a parcel, so a second upload of the same khasra number is
visibly the same row, not a second unrelated one.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_READ_DOCUMENTS, require_roles
from app.models.document import Document
from app.models.finding import Finding, LandEvent
from app.models.ocr import Claim
from app.models.parcel import Parcel, ParcelIdentifierAlias, Person
from app.models.user import User
from app.services.analysis_service import analysis_service
from app.services.evidence_sufficiency_scorer import evidence_sufficiency_scorer
from app.services.identity_resolver import normalize_identifier
from app.services.timeline_builder import timeline_builder
from app.services.transition_analyzer import transition_analyzer

router = APIRouter(prefix="/parcels", tags=["Parcels"])


def _parcel_summary(db: Session, p: Parcel) -> Dict[str, Any]:
    document_count = (
        db.query(Claim.document_id)
        .filter(Claim.parcel_id == p.id, Claim.lifecycle_status == "ACCEPTED")
        .distinct()
        .count()
    )
    return {
        "id": p.id,
        "parcel_key": p.parcel_key,
        "state": p.state,
        "district": p.district,
        "tehsil": p.tehsil,
        "village": p.village,
        "khasra_number": p.khasra_number_norm,
        "khata_number": p.khata_number_norm,
        "status": p.status,
        "first_seen_year": p.first_seen_year,
        "last_seen_year": p.last_seen_year,
        "document_count": document_count,
    }


@router.get("")
def search_parcels(
    q: str = Query(..., min_length=1, description="Khasra/khata number or village name, any script/separator"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    q_norm = normalize_identifier(q)
    conditions = [Parcel.village.ilike(f"%{q}%")]
    if q_norm:
        conditions.append(Parcel.khasra_number_norm.ilike(f"%{q_norm}%"))
        conditions.append(Parcel.khata_number_norm.ilike(f"%{q_norm}%"))
    matches = (
        db.query(Parcel)
        .filter(or_(*conditions))
        .order_by(Parcel.updated_at.desc())
        .limit(50)
        .all()
    )
    return {"query": q, "count": len(matches), "parcels": [_parcel_summary(db, p) for p in matches]}


@router.get("/{parcel_id}")
def get_parcel(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    claims = (
        db.query(Claim)
        .filter(Claim.parcel_id == parcel.id, Claim.lifecycle_status == "ACCEPTED")
        .order_by(Claim.document_id, Claim.standardized_field)
        .all()
    )
    doc_ids = sorted({c.document_id for c in claims})
    docs = db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else []

    person_ids = sorted({c.person_id for c in claims if c.person_id})
    persons = db.query(Person).filter(Person.id.in_(person_ids)).all() if person_ids else []

    aliases = db.query(ParcelIdentifierAlias).filter(ParcelIdentifierAlias.parcel_id == parcel.id).all()

    return {
        "parcel": _parcel_summary(db, parcel),
        "aliases": [
            {
                "raw_identifier": a.raw_identifier,
                "normalized": a.normalized,
                "match_method": a.match_method,
                "confidence": a.confidence,
            }
            for a in aliases
        ],
        "documents": [
            {
                "id": d.id,
                "file_name": d.file_name,
                "document_year": d.document_year,
                "status": d.status,
                "source_class": d.source_class,
            }
            for d in docs
        ],
        "persons": [
            {"id": p.id, "canonical_name": p.canonical_name}
            for p in persons
        ],
        "claims": [
            {
                "id": c.id,
                "document_id": c.document_id,
                "standardized_field": c.standardized_field,
                "field_value": c.field_value,
                "confidence": c.confidence,
                "person_id": c.person_id,
            }
            for c in claims
        ],
    }


@router.get("/{parcel_id}/timeline")
def get_parcel_timeline(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    """
    Phase 4 gate (BHUMI_FORENSICS_SPEC.md §9): "Timeline API returns real
    snapshots from real claims." Snapshots and transitions are computed live
    from currently-ACCEPTED claims on every call — see timeline_builder.py's
    docstring for why this phase doesn't persist a snapshot table.
    """
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")

    snapshots = timeline_builder.build(db, parcel_id)
    transitions = transition_analyzer.analyze(snapshots)
    # Phase 5: fill explained_by_event_id / match_confidence by matching each
    # transition against the parcel's stored LandEvents. Unmatched material
    # transitions are surfaced as EVIDENCE_GAP findings (see /findings), not
    # labelled here.
    transitions = analysis_service.resolve_transition_events(db, parcel_id, transitions)

    return {
        "parcel": _parcel_summary(db, parcel),
        "snapshots": [s.as_dict() for s in snapshots],
        "transitions": transitions,
    }


def _event_dict(e: LandEvent) -> Dict[str, Any]:
    return {
        "id": e.id,
        "event_type": e.event_type,
        "event_date": e.event_date,
        "order_number": e.order_number,
        "from_person_id": e.from_person_id,
        "to_person_id": e.to_person_id,
        "area_before": e.area_before,
        "area_after": e.area_after,
        "evidence_claim_ids": e.evidence_claim_ids or [],
        "source_document_id": e.source_document_id,
        "confidence": e.confidence,
        "engine_version": e.engine_version,
    }


@router.get("/{parcel_id}/events")
def get_parcel_events(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    """LandEvents extracted from this parcel's documents (mutations, registrations)."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    events = (
        db.query(LandEvent)
        .filter(LandEvent.parcel_id == parcel_id)
        .order_by(LandEvent.event_date, LandEvent.id)
        .all()
    )
    return {"parcel_id": parcel_id, "count": len(events), "events": [_event_dict(e) for e in events]}


@router.get("/{parcel_id}/findings")
def get_parcel_findings(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    """Investigation signals for this parcel — contradictions and evidence gaps."""
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    findings = db.query(Finding).filter(Finding.parcel_id == parcel_id).all()
    _order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    findings.sort(key=lambda f: (_order.get(f.severity, 9), -(f.id or 0)))
    return {
        "parcel_id": parcel_id,
        "count": len(findings),
        "findings": [
            {
                "id": f.id,
                "finding_type": f.finding_type,
                "severity": f.severity,
                "affected_predicates": f.affected_predicates or [],
                "time_range": {"start": f.time_range_start, "end": f.time_range_end},
                "explanation": (
                    f.explanation_template.format(**(f.explanation_params_json or {}))
                    if f.explanation_params_json
                    else f.explanation_template
                ),
                "recommended_action": f.recommended_action,
                "resolution_status": f.resolution_status,
                "source_claim_ids": f.source_claim_ids or [],
                "source_document_ids": f.source_document_ids or [],
            }
            for f in findings
        ],
    }


@router.get("/{parcel_id}/sufficiency")
def get_parcel_sufficiency(
    parcel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    """
    Phase 6 gate (BHUMI_FORENSICS_SPEC.md §9): "Score breakdown visible and
    reproducible." Computed live (like the timeline) rather than read from
    the persisted table — see evidence_sufficiency_scorer.py's module
    docstring for the full six-component formula and why each component can
    report `available: false` instead of a guessed number.
    """
    parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="Parcel not found")
    score = evidence_sufficiency_scorer.score_parcel(db, parcel_id)
    return score.as_dict()
