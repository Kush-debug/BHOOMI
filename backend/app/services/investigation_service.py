"""
Investigation orchestration (BHUMI_FORENSICS_SPEC.md §4 step 11 SCORE — Phase 6).

Ties Phase 5's findings to Phase 6's scoring for one parcel:

    parcel               -> EvidenceSufficiencyScorer.score_parcel  -> persisted breakdown
    each active finding  -> Finding.evidence_sufficiency = parcel score (see scorer docstring)
                          -> PriorityScorer.score_finding             -> priority_score/band
    all active findings  -> one InvestigationCase per parcel, reconciled

"Active" = resolution_status in (OPEN, IN_REVIEW) — a finding a human is
still actively working (IN_REVIEW) is not yet resolved and still belongs in
the priority queue; RESOLVED/DISMISSED findings are done and drop out.

Same reconciliation discipline as `analysis_service`: an `InvestigationCase`
already moved off OPEN, or with an officer assigned, is refreshed (new
finding_ids/priority) but never has its officer-owned fields touched, and is
never auto-closed by regeneration even if its findings have all resolved —
that closure is the officer's call once Phase 7 gives them a way to make it.

Never fatal: called from the processing pipeline in a try/except, exactly
like ANALYSE. A scoring error leaves prior scores/cases untouched rather
than blocking a document from finishing.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.finding import Finding
from app.models.investigation import STATUS_OPEN, InvestigationCase
from app.models.sufficiency import EvidenceSufficiencyScore
from app.services.evidence_sufficiency_scorer import SufficiencyScore, evidence_sufficiency_scorer
from app.services.priority_scorer import priority_scorer

ENGINE_VERSION = "phase6-investigation-v1"
_ACTIVE_STATUSES = ("OPEN", "IN_REVIEW")

# Default SLA windows by band, applied once when a case is first opened.
# Config, not a literal in the create path.
SLA_DAYS_BY_BAND = {"CRITICAL": 3, "HIGH": 7, "MEDIUM": 14, "LOW": 30}


def _upsert_sufficiency_row(db: Session, score: SufficiencyScore) -> EvidenceSufficiencyScore:
    row = (
        db.query(EvidenceSufficiencyScore)
        .filter(EvidenceSufficiencyScore.scope_type == score.scope_type, EvidenceSufficiencyScore.scope_id == score.scope_id)
        .first()
    )
    if row is None:
        row = EvidenceSufficiencyScore(scope_type=score.scope_type, scope_id=score.scope_id)
        db.add(row)
    row.formula_version = score.formula_version
    row.components_json = {name: c.as_dict() for name, c in score.components.items()}
    row.overall_score = score.overall_score
    return row


class InvestigationService:
    def score_and_prioritize_parcel(self, db: Session, parcel_id: int) -> Dict[str, object]:
        parcel_score = evidence_sufficiency_scorer.score_parcel(db, parcel_id)
        _upsert_sufficiency_row(db, parcel_score)

        active_findings: List[Finding] = (
            db.query(Finding)
            .filter(Finding.parcel_id == parcel_id, Finding.resolution_status.in_(_ACTIVE_STATUSES))
            .all()
        )

        priorities: Dict[int, float] = {}
        bands: Dict[int, str] = {}
        best_finding = None
        best_priority = -1.0

        for finding in active_findings:
            finding.evidence_sufficiency = parcel_score.overall_score
            finding_score = evidence_sufficiency_scorer.score_finding(db, finding.id, parcel_id)
            _upsert_sufficiency_row(db, finding_score)

            pscore = priority_scorer.score_finding(db, finding, parcel_score.overall_score)
            if pscore.score is not None:
                priorities[finding.id] = pscore.score
                bands[finding.id] = pscore.band
                if pscore.score > best_priority:
                    best_priority = pscore.score
                    best_finding = (finding, pscore)

        case_summary = self._reconcile_case(db, parcel_id, active_findings, best_finding)
        db.flush()

        return {
            "parcel_id": parcel_id,
            "parcel_sufficiency": parcel_score.overall_score,
            "findings_scored": len(active_findings),
            "case": case_summary,
            "engine_version": ENGINE_VERSION,
        }

    def _reconcile_case(self, db: Session, parcel_id: int, active_findings: List[Finding], best) -> Dict[str, object]:
        case = db.query(InvestigationCase).filter(InvestigationCase.parcel_id == parcel_id).first()

        if not active_findings:
            # Nothing left to investigate. If the case is still fully
            # system-owned (never assigned, still OPEN) it's safe to remove —
            # the condition that created it no longer holds, same rule
            # analysis_service applies to findings. An officer-touched case
            # is left exactly alone; closing it is their call (Phase 7).
            if case is not None and not case.is_officer_owned:
                db.delete(case)
                return {"action": "removed", "reason": "no active findings remain"}
            if case is not None:
                return {"action": "preserved", "id": case.id, "reason": "officer-owned; not auto-closed"}
            return {"action": "none"}

        if best is None:
            # Findings exist but none produced a computable priority (every
            # term was unavailable) — leave any existing case's priority
            # fields alone rather than overwriting a real number with None.
            if case is None:
                return {"action": "skipped", "reason": "no finding produced a computable priority yet"}
            case.finding_ids = [f.id for f in active_findings]
            return {"action": "updated_findings_only", "id": case.id}

        winning_finding, winning_priority = best
        finding_ids = [f.id for f in active_findings]

        if case is None:
            case = InvestigationCase(
                parcel_id=parcel_id,
                status=STATUS_OPEN,
                sla_due_at=None,
            )
            db.add(case)
            db.flush()  # need case.opened_at populated for the SLA calc below via default
            sla_days = SLA_DAYS_BY_BAND.get(winning_priority.band)
            if sla_days is not None and case.opened_at:
                case.sla_due_at = case.opened_at + timedelta(days=sla_days)
            case.finding_ids = finding_ids
            case.priority_score = winning_priority.score
            case.priority_band = winning_priority.band
            case.priority_breakdown_json = winning_priority.as_dict()
            case.engine_version = ENGINE_VERSION
            return {"action": "created", "id": case.id, "priority_band": case.priority_band}

        # Existing case: always refresh finding_ids + priority (an officer
        # still benefits from a current score) but never touch assigned_to /
        # status / comments / resolution / sla_due_at once they're officer-owned.
        case.finding_ids = finding_ids
        case.priority_score = winning_priority.score
        case.priority_band = winning_priority.band
        case.priority_breakdown_json = winning_priority.as_dict()
        case.engine_version = ENGINE_VERSION
        return {"action": "updated", "id": case.id, "priority_band": case.priority_band,
                "officer_owned": case.is_officer_owned}


investigation_service = InvestigationService()
