"""
PriorityScorer (BHUMI_FORENSICS_SPEC.md §5.9 — Phase 6).

"Which open findings should an officer look at first?"

    priority = w1*severity + w2*(1 - evidence_sufficiency) + w3*ownership_involved
             + w4*area_magnitude + w5*staleness

Deterministic, with every contributing term returned alongside the score
(spec: "the contributing terms returned alongside the score so the ordering
is explainable"). Bands: CRITICAL / HIGH / MEDIUM / LOW.

Same unavailable-component handling as EvidenceSufficiencyScorer: a term
that can't honestly be computed for a given finding (e.g. no evidence
sufficiency yet, or an area finding whose magnitude can't be recovered) is
excluded and the remaining weights renormalised, rather than defaulted to a
number that would silently under- or over-rate the finding.

`area_magnitude` deliberately recomputes rather than reads a stored number:
neither `Finding.source_claim_ids` (empty for EVIDENCE_GAP — a gap isn't
"from" any one claim) nor `explanation_params_json` carries a raw numeric
delta, only the rendered sentence. Recomputing from the live evidence layer
at scoring time — the same "derived, not cached" approach Phase 4 already
uses for the timeline itself — avoids adding a stored field to `Finding`
(and therefore avoids touching the already-verified Phase 5 migration/model)
just to carry a number that's cheap to regenerate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.finding import FINDING_CONTRADICTION, FINDING_EVIDENCE_GAP, Finding
from app.services.timeline_builder import timeline_builder
from app.services.transition_analyzer import transition_analyzer

FORMULA_VERSION = "phase6-priority-v1"

DEFAULT_WEIGHTS: Dict[str, float] = {
    "severity": 0.35,
    "evidence_gap": 0.25,      # w2 * (1 - evidence_sufficiency)
    "ownership_involved": 0.15,
    "area_magnitude": 0.15,
    "staleness": 0.10,
}

SEVERITY_SCORE = {"CRITICAL": 1.0, "HIGH": 0.75, "MEDIUM": 0.5, "LOW": 0.25}

# A "material" area change is capped at this magnitude for scoring purposes —
# a 200% area blowup and a 45% one are both "as bad as it gets" for priority,
# not linearly unbounded. Config, not a literal buried in the formula.
AREA_MAGNITUDE_SATURATION_PCT = 50.0
STALENESS_HORIZON_DAYS = 30.0  # an OPEN finding older than this is "fully stale" for priority purposes

BAND_THRESHOLDS = (("CRITICAL", 0.75), ("HIGH", 0.55), ("MEDIUM", 0.35))  # else LOW


@dataclass
class PriorityTerm:
    value: Optional[float]
    weight: float
    available: bool
    basis: str

    def as_dict(self) -> dict:
        return {"value": self.value, "weight": self.weight, "available": self.available, "basis": self.basis}


@dataclass
class PriorityScore:
    finding_id: int
    score: Optional[float]
    band: Optional[str]
    terms: Dict[str, PriorityTerm] = field(default_factory=dict)
    formula_version: str = FORMULA_VERSION
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "score": self.score,
            "band": self.band,
            "formula_version": self.formula_version,
            "computed_at": self.computed_at.isoformat(),
            "terms": {name: t.as_dict() for name, t in self.terms.items()},
        }


def _band(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    for name, threshold in BAND_THRESHOLDS:
        if score >= threshold:
            return name
    return "LOW"


def _parse_float(text: str) -> Optional[float]:
    try:
        return float(text.strip())
    except (TypeError, ValueError, AttributeError):
        return None


class PriorityScorer:
    def _severity_term(self, finding: Finding) -> PriorityTerm:
        value = SEVERITY_SCORE.get(finding.severity)
        if value is None:
            return PriorityTerm(None, DEFAULT_WEIGHTS["severity"], False, f"unrecognised severity '{finding.severity}'")
        return PriorityTerm(value, DEFAULT_WEIGHTS["severity"], True, f"severity={finding.severity}")

    def _evidence_gap_term(self, evidence_sufficiency: Optional[float]) -> PriorityTerm:
        if evidence_sufficiency is None:
            return PriorityTerm(None, DEFAULT_WEIGHTS["evidence_gap"], False,
                                 "parcel evidence sufficiency not yet computable")
        return PriorityTerm(round(1.0 - evidence_sufficiency, 4), DEFAULT_WEIGHTS["evidence_gap"], True,
                             f"1 - evidence_sufficiency ({evidence_sufficiency})")

    def _ownership_term(self, finding: Finding) -> PriorityTerm:
        involved = "owner_name" in (finding.affected_predicates or [])
        return PriorityTerm(1.0 if involved else 0.0, DEFAULT_WEIGHTS["ownership_involved"], True,
                             "owner_name in affected_predicates" if involved else "ownership not affected")

    def _area_magnitude_term(self, db: Session, finding: Finding) -> PriorityTerm:
        pct: Optional[float] = None
        basis = ""

        if finding.finding_type == FINDING_EVIDENCE_GAP:
            # Recompute this parcel's transitions live and find the one this
            # finding was raised for (same (from_year, to_year) window) —
            # see module docstring for why this isn't a stored field.
            snapshots = timeline_builder.build(db, finding.parcel_id)
            transitions = transition_analyzer.analyze(snapshots)
            match = next(
                (
                    t for t in transitions
                    if t["from_year"] == finding.time_range_start and t["to_year"] == finding.time_range_end
                ),
                None,
            )
            if match and match.get("area_delta_pct") is not None:
                pct = abs(match["area_delta_pct"])
                basis = f"|area_delta_pct|={pct:.1f}% from the matching transition"
        elif finding.finding_type == FINDING_CONTRADICTION and "area" in (finding.affected_predicates or []):
            raw_values = (finding.explanation_params_json or {}).get("values", "")
            parsed = [_parse_float(v) for v in str(raw_values).split(",")]
            parsed = [v for v in parsed if v is not None]
            if len(parsed) >= 2 and max(parsed) > 0:
                pct = abs(max(parsed) - min(parsed)) / max(parsed) * 100.0
                basis = f"relative spread of contradictory area values ({parsed}) = {pct:.1f}%"

        if pct is None:
            return PriorityTerm(None, DEFAULT_WEIGHTS["area_magnitude"], False,
                                 "not an area-related finding, or the magnitude could not be recovered")
        value = max(0.0, min(1.0, pct / AREA_MAGNITUDE_SATURATION_PCT))
        return PriorityTerm(round(value, 4), DEFAULT_WEIGHTS["area_magnitude"], True, basis)

    def _staleness_term(self, finding: Finding) -> PriorityTerm:
        if not finding.created_at:
            return PriorityTerm(None, DEFAULT_WEIGHTS["staleness"], False, "no created_at recorded")
        age_days = (datetime.utcnow() - finding.created_at).total_seconds() / 86400.0
        value = max(0.0, min(1.0, age_days / STALENESS_HORIZON_DAYS))
        return PriorityTerm(round(value, 4), DEFAULT_WEIGHTS["staleness"], True,
                             f"open {age_days:.1f}d / {STALENESS_HORIZON_DAYS:.0f}d horizon")

    def score_finding(self, db: Session, finding: Finding, evidence_sufficiency: Optional[float]) -> PriorityScore:
        terms: Dict[str, PriorityTerm] = {
            "severity": self._severity_term(finding),
            "evidence_gap": self._evidence_gap_term(evidence_sufficiency),
            "ownership_involved": self._ownership_term(finding),
            "area_magnitude": self._area_magnitude_term(db, finding),
            "staleness": self._staleness_term(finding),
        }
        available = {k: t for k, t in terms.items() if t.available and t.value is not None}
        if not available:
            score = None
        else:
            total_weight = sum(t.weight for t in available.values())
            score = round(sum(t.value * t.weight for t in available.values()) / total_weight, 4) if total_weight else None

        return PriorityScore(finding_id=finding.id, score=score, band=_band(score), terms=terms)


priority_scorer = PriorityScorer()
