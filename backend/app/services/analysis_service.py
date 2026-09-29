"""
Analysis orchestration (BHUMI_FORENSICS_SPEC.md §4 step 10 ANALYSE — Phase 5).

Ties Phase 4's reconstruction to Phase 5's detection for one parcel:

    documents -> LandEvents            (event_extraction_service)
    claims    -> snapshots/transitions (timeline_builder / transition_analyzer)
    transition + events -> match       (event_matcher)   -> explained_by_event_id
    unmatched material transition      -> EVIDENCE_GAP Finding
    conflicting same-year claims       -> CONTRADICTION Finding   (contradiction_engine)

Regeneration rule: this replaces only findings that are still OPEN and
system-owned. The moment an officer moves a finding to IN_REVIEW / RESOLVED /
DISMISSED it is theirs — reprocessing the document never overwrites or
deletes it (spec §2 rule 4, applied to the investigation layer).

Never fatal: called from the processing pipeline in a try/except. A parcel
with no khasra number, or an analysis error, leaves the previous findings
untouched rather than blocking a document from finishing.
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.finding import (
    FINDING_CONTRADICTION,
    FINDING_EVIDENCE_GAP,
    LandEvent,
    Finding,
    RES_OPEN,
)
from app.models.document import Document
from app.models.ocr import Claim
from app.models.parcel import Parcel
from app.services.contradiction_engine import contradiction_engine
from app.services.event_extraction_service import event_extraction_service
from app.services.event_matcher import EventLike, event_matcher
from app.services.timeline_builder import timeline_builder
from app.services.transition_analyzer import transition_analyzer

ENGINE_VERSION = "phase5-analysis-v1"

_PREDICATE_LABEL = {
    "owner_name": "the owner",
    "area": "the recorded area",
    "classification": "the land classification",
    "land_classification": "the land classification",
    "khata_number": "the khata number",
}


def _documents_for_parcel(db: Session, parcel_id: int) -> List[Document]:
    doc_ids = [
        row[0]
        for row in db.query(Claim.document_id)
        .filter(Claim.parcel_id == parcel_id, Claim.lifecycle_status == "ACCEPTED")
        .distinct()
        .all()
    ]
    if not doc_ids:
        return []
    return db.query(Document).filter(Document.id.in_(doc_ids)).all()


def _events_as_matchable(events: List[LandEvent]) -> List[EventLike]:
    return [
        EventLike(
            id=e.id,
            event_type=e.event_type,
            event_date=e.event_date,
            to_person_id=e.to_person_id,
            confidence=e.confidence,
        )
        for e in events
    ]


def _change_summary(transition: Dict[str, Any]) -> str:
    parts: List[str] = []
    od = transition.get("ownership_delta")
    if od:
        parts.append(f"ownership changed ({od.get('from_name') or '?'} to {od.get('to_name') or '?'})")
    if transition.get("area_delta_abs") not in (None, 0):
        pct = transition.get("area_delta_pct")
        pct_txt = f" ({pct:+.1f}%)" if pct is not None else ""
        parts.append(
            f"area changed {transition.get('area_delta_abs'):+.4f}{pct_txt}".replace("+-", "-")
        )
    cd = transition.get("classification_delta")
    if cd:
        parts.append(f"classification changed ({cd.get('from')} to {cd.get('to')})")
    return "; ".join(parts) or "a material change occurred"


def _evidence_gap_severity(transition: Dict[str, Any]) -> str:
    owner = bool(transition.get("ownership_delta"))
    area_material = (
        transition.get("area_delta_pct") is not None
        and abs(transition["area_delta_pct"]) > transition.get("area_tolerance_pct", 1.0)
    )
    if owner and area_material:
        return "CRITICAL"
    if owner:
        return "HIGH"
    if area_material:
        return "MEDIUM"
    return "LOW"


class AnalysisService:
    # -- transition annotation (used by the timeline endpoint) -------------

    def resolve_transition_events(
        self, db: Session, parcel_id: int, transitions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Fill `explained_by_event_id` / `match_confidence` on each transition
        by matching it against the parcel's stored LandEvents. Pure read."""
        events = _events_as_matchable(
            db.query(LandEvent).filter(LandEvent.parcel_id == parcel_id).all()
        )
        for t in transitions:
            result = event_matcher.match(t, events)
            t["explained_by_event_id"] = result.event_id
            t["match_confidence"] = result.match_confidence
            t["match_basis"] = result.basis
        return transitions

    # -- full regeneration (used by the processing pipeline) --------------

    def analyze_parcel(self, db: Session, parcel_id: int) -> Dict[str, Any]:
        parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
        if not parcel:
            return {"parcel_id": parcel_id, "skipped": "parcel not found"}

        # 1. events from each document's own claims
        for doc in _documents_for_parcel(db, parcel_id):
            event_extraction_service.extract_events_for_document(db, doc, parcel_id)
        db.flush()

        # 2. reconstruction (Phase 4, computed live)
        snapshots = timeline_builder.build(db, parcel_id)
        transitions = transition_analyzer.analyze(snapshots)

        # 3. match transitions to events
        events = db.query(LandEvent).filter(LandEvent.parcel_id == parcel_id).all()
        matchable = _events_as_matchable(events)

        desired: Dict[str, Dict[str, Any]] = {}

        for t in transitions:
            if not t.get("is_material"):
                continue
            result = event_matcher.match(t, matchable)
            if result.event_id is not None:
                continue  # explained — no finding
            key = (
                f"{parcel_id}:{FINDING_EVIDENCE_GAP}:{t['from_year']}:{t['to_year']}:"
                f"{'|'.join(sorted(t.get('changed_predicates', [])))}"
            )
            desired[key] = self._evidence_gap_finding(parcel, t, key)

        # 4. contradictions
        for c in contradiction_engine.detect(db, parcel_id):
            key = f"{parcel_id}:{FINDING_CONTRADICTION}:{c['year']}:{c['predicate']}"
            desired[key] = self._contradiction_finding(parcel, c, key)

        # 5. upsert — replace only OPEN, system-owned findings
        summary = self._reconcile_findings(db, parcel_id, desired)
        summary.update(
            {
                "parcel_id": parcel_id,
                "snapshots": len(snapshots),
                "transitions": len(transitions),
                "events": len(events),
                "engine_version": ENGINE_VERSION,
            }
        )
        return summary

    # -- finding builders -------------------------------------------------

    def _evidence_gap_finding(self, parcel: Parcel, t: Dict[str, Any], dedupe_key: str) -> Dict[str, Any]:
        khasra = parcel.khasra_number_norm
        tehsil = parcel.tehsil or "the tehsil"
        summary = _change_summary(t)
        template = (
            "Between {from_year} and {to_year}, {change_summary} for Khasra {khasra}, {tehsil}, "
            "with no mutation, partition or registration record on file that accounts for it."
        )
        params = {
            "from_year": t["from_year"],
            "to_year": t["to_year"],
            "change_summary": summary,
            "khasra": khasra,
            "tehsil": tehsil,
        }
        return {
            "finding_type": FINDING_EVIDENCE_GAP,
            "parcel_id": parcel.id,
            "severity": _evidence_gap_severity(t),
            "affected_predicates": t.get("changed_predicates", []),
            "time_range_start": t["from_year"],
            "time_range_end": t["to_year"],
            "source_claim_ids": [],
            "source_document_ids": [],
            "rule_id": "evidence_gap.material_transition_unmatched",
            "rule_version": "v1",
            "explanation_template": template,
            "explanation_params_json": params,
            "recommended_action": (
                f"Retrieve the mutation register and any partition or registration orders for "
                f"Khasra {khasra}, {tehsil}, covering {t['from_year']}–{t['to_year']}."
            ),
            "dedupe_key": dedupe_key,
        }

    def _contradiction_finding(self, parcel: Parcel, c: Dict[str, Any], dedupe_key: str) -> Dict[str, Any]:
        label = _PREDICATE_LABEL.get(c["predicate"], c["predicate"])
        template = (
            "Two independent documents describe {label} for Khasra {khasra} in {year} differently: "
            "{values}. Both remain on file; neither is marked incorrect."
        )
        params = {
            "label": label,
            "khasra": parcel.khasra_number_norm,
            "year": c["year"],
            "values": ", ".join(c["values"]),
        }
        severity = "HIGH" if c["predicate"] == "owner_name" else "MEDIUM"
        return {
            "finding_type": FINDING_CONTRADICTION,
            "parcel_id": parcel.id,
            "severity": severity,
            "affected_predicates": [c["predicate"]],
            "time_range_start": c["year"],
            "time_range_end": c["year"],
            "source_claim_ids": c["source_claim_ids"],
            "source_document_ids": c["source_document_ids"],
            "rule_id": "contradiction.same_year_independent_documents",
            "rule_version": "v1",
            "explanation_template": template,
            "explanation_params_json": params,
            "recommended_action": (
                f"Compare source documents {c['source_document_ids']} and record which reflects the "
                f"correct value of {label} for {c['year']}, or escalate for field verification."
            ),
            "dedupe_key": dedupe_key,
        }

    # -- reconciliation --------------------------------------------------

    def _reconcile_findings(
        self, db: Session, parcel_id: int, desired: Dict[str, Dict[str, Any]]
    ) -> Dict[str, int]:
        existing = db.query(Finding).filter(Finding.parcel_id == parcel_id).all()
        existing_by_key = {f.dedupe_key: f for f in existing}

        created = updated = removed = preserved = 0

        for key, payload in desired.items():
            row = existing_by_key.get(key)
            if row is None:
                db.add(Finding(**payload, resolution_status=RES_OPEN, engine_version=ENGINE_VERSION))
                created += 1
            elif row.is_officer_owned:
                preserved += 1
            else:
                for attr, value in payload.items():
                    setattr(row, attr, value)
                updated += 1

        for key, row in existing_by_key.items():
            if key in desired:
                continue
            if row.is_officer_owned:
                preserved += 1
                continue
            db.delete(row)  # the condition that raised it no longer holds
            removed += 1

        db.flush()
        return {"findings_created": created, "findings_updated": updated,
                "findings_removed": removed, "findings_preserved": preserved}


analysis_service = AnalysisService()
