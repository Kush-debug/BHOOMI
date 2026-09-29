"""
EvidenceSufficiencyScorer (BHUMI_FORENSICS_SPEC.md §5.7 — Phase 6).

"How much should we trust what we currently believe about this parcel?"

Six components, published weights (spec §5.7 table), every one computed from
stored data — never a constant:

| Component | Computed from | Default weight |
|---|---|---|
| extraction_quality | mean OCR word confidence of EvidenceRegions backing this parcel's accepted claims | 0.20 |
| cross_document_agreement | fraction of independent documents agreeing, averaged over predicates with >=2 documents | 0.20 |
| temporal_continuity | fraction of consecutive snapshot-year gaps within a configurable "well-covered" span | 0.15 |
| event_evidence | fraction of material transitions with a matched, document-backed LandEvent | 0.25 |
| identity_confidence | weakest parcel/person alias match method actually used (EXACT=1.0, ALIAS=0.85, FUZZY=0.5) | 0.10 |
| spatial_consistency | \\|area_claimed - area_from_geometry\\| / area_claimed, only when a SURVEYED GISParcel exists | 0.10 |

**Unavailable components are excluded and the remaining weights renormalised**
(spec §5.7) — never defaulted to a filler number. `formula_version` is
stored on every score so a historical score stays interpretable even after
the weights or method change.

Two entry points, for two different honesty reasons:

`score_parcel` — the real, full six-component score, computed *after* a
parcel's timeline/transitions/events exist. This is what's persisted
(`EvidenceSufficiencyScore`) and what populates `Finding.evidence_sufficiency`.

`claim_ranking_score` — a narrower 3-component score (extraction_quality,
cross_document_agreement, identity_confidence) used by `TimelineBuilder` to
pick the winning claim within a (year, predicate) group. It deliberately
excludes `temporal_continuity`, `event_evidence`, and `spatial_consistency`:
those need the timeline/transitions to already exist, and the timeline is
the thing being built. Scoring a candidate claim with "how good is the
timeline this claim will help produce" would be circular. This is flagged
here and in `timeline_builder.py`, not hidden — `claim_ranking_score` is a
real, computed, non-fabricated signal, just an honestly narrower one than
the full published formula.

A finding's sufficiency (`score_finding`) is, by design, its parcel's
`score_parcel` result at scoring time — the spec's component table describes
parcel-wide signals, not a per-finding variant, and inventing a
finding-specific formula the spec doesn't define would be exactly the kind
of unsupported precision this project's honesty rules forbid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.finding import LandEvent
from app.models.gis import GISParcel
from app.models.ocr import Claim
from app.models.parcel import Parcel, ParcelIdentifierAlias, PersonAlias
from app.services.event_matcher import EventLike, event_matcher
from app.services.identity_resolver import normalize_identifier
from app.services.timeline_builder import SNAPSHOT_PREDICATES, timeline_builder
from app.services.transition_analyzer import transition_analyzer

FORMULA_VERSION = "phase6-sufficiency-v1"

DEFAULT_WEIGHTS: Dict[str, float] = {
    "extraction_quality": 0.20,
    "cross_document_agreement": 0.20,
    "temporal_continuity": 0.15,
    "event_evidence": 0.25,
    "identity_confidence": 0.10,
    "spatial_consistency": 0.10,
}

# Config, not literals (matches the pattern set by TransitionConfig in Phase 4).
TEMPORAL_WELL_COVERED_GAP_YEARS = 5
MATCH_METHOD_SCORE = {"EXACT": 1.0, "ALIAS": 0.85, "FUZZY": 0.5}

# Only unit pairs with a fixed, non-regional conversion factor are compared.
# "bigha"/"biswa" vary by state and era with no single correct factor —
# fabricating one would be worse than reporting the component unavailable.
_FIXED_UNIT_TO_SQM = {"hectare": 10000.0, "acre": 4046.8564224, "sq_meter": 1.0}

_CHECKED_PREDICATES = SNAPSHOT_PREDICATES  # owner_name, area, land_classification, khata_number


@dataclass
class ComponentScore:
    value: Optional[float]
    weight: float
    available: bool
    basis: str

    def as_dict(self) -> dict:
        return {"value": self.value, "weight": self.weight, "available": self.available, "basis": self.basis}


@dataclass
class SufficiencyScore:
    scope_type: str
    scope_id: int
    overall_score: Optional[float]
    components: Dict[str, ComponentScore] = field(default_factory=dict)
    formula_version: str = FORMULA_VERSION
    computed_at: datetime = field(default_factory=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "overall_score": self.overall_score,
            "formula_version": self.formula_version,
            "computed_at": self.computed_at.isoformat(),
            "components": {name: c.as_dict() for name, c in self.components.items()},
        }


def _combine(components: Dict[str, ComponentScore]) -> Optional[float]:
    available = {k: c for k, c in components.items() if c.available and c.value is not None}
    if not available:
        return None
    total_weight = sum(c.weight for c in available.values())
    if total_weight <= 0:
        return None
    return round(sum(c.value * c.weight for c in available.values()) / total_weight, 4)


class EvidenceSufficiencyScorer:
    # -- components, each independently computable and independently testable --

    def _extraction_quality(self, db: Session, parcel_id: int) -> ComponentScore:
        # EvidenceRegion is imported here rather than at module level solely
        # to keep this module's import graph flat and easy to reason about;
        # unlike TimelineBuilder, there's no cycle risk here — it's a style
        # choice, not a workaround.
        from app.models.ocr import EvidenceRegion

        region_ids = [
            row[0]
            for row in db.query(Claim.evidence_region_id)
            .filter(
                Claim.parcel_id == parcel_id,
                Claim.lifecycle_status == "ACCEPTED",
                Claim.evidence_region_id.isnot(None),
            )
            .all()
        ]
        if not region_ids:
            return ComponentScore(None, DEFAULT_WEIGHTS["extraction_quality"], False,
                                   "no accepted claim on this parcel links to an OCR evidence region")
        values = [
            v[0]
            for v in db.query(EvidenceRegion.ocr_confidence)
            .filter(EvidenceRegion.id.in_(region_ids), EvidenceRegion.ocr_confidence.isnot(None))
            .all()
        ]
        if not values:
            return ComponentScore(None, DEFAULT_WEIGHTS["extraction_quality"], False,
                                   "linked evidence regions have no recorded OCR confidence")
        mean_conf = sum(values) / len(values)
        return ComponentScore(round(mean_conf, 4), DEFAULT_WEIGHTS["extraction_quality"], True,
                               f"mean OCR confidence over {len(values)} evidence region(s)")

    def _cross_document_agreement(self, db: Session, parcel_id: int) -> ComponentScore:
        claims = (
            db.query(Claim)
            .filter(
                Claim.parcel_id == parcel_id,
                Claim.lifecycle_status == "ACCEPTED",
                Claim.standardized_field.in_(_CHECKED_PREDICATES),
            )
            .join(Claim.document)
            .all()
        )
        groups: Dict[tuple, List[Claim]] = {}
        for c in claims:
            groups.setdefault((c.document.document_year, c.standardized_field), []).append(c)

        fractions = []
        for group in groups.values():
            doc_values: Dict[int, str] = {c.document_id: (c.field_value or "").strip().casefold() for c in group}
            if len(doc_values) < 2:
                continue  # only one document ever asserted this (year, predicate) - nothing to agree/disagree
            counts: Dict[str, int] = {}
            for v in doc_values.values():
                counts[v] = counts.get(v, 0) + 1
            majority = max(counts.values())
            fractions.append(majority / len(doc_values))

        if not fractions:
            return ComponentScore(None, DEFAULT_WEIGHTS["cross_document_agreement"], False,
                                   "no (year, predicate) is independently corroborated by >=2 documents yet")
        value = sum(fractions) / len(fractions)
        return ComponentScore(round(value, 4), DEFAULT_WEIGHTS["cross_document_agreement"], True,
                               f"averaged over {len(fractions)} multi-document (year, predicate) group(s)")

    def _temporal_continuity(self, snapshot_years: List[int]) -> ComponentScore:
        if len(snapshot_years) < 2:
            return ComponentScore(None, DEFAULT_WEIGHTS["temporal_continuity"], False,
                                   "fewer than two evidenced years on file - no gaps to measure")
        gaps = [b - a for a, b in zip(snapshot_years, snapshot_years[1:])]
        covered = sum(1 for g in gaps if g <= TEMPORAL_WELL_COVERED_GAP_YEARS)
        value = covered / len(gaps)
        return ComponentScore(round(value, 4), DEFAULT_WEIGHTS["temporal_continuity"], True,
                               f"{covered}/{len(gaps)} consecutive year-gaps <= {TEMPORAL_WELL_COVERED_GAP_YEARS}y")

    def _event_evidence(self, db: Session, parcel_id: int, transitions: List[dict]) -> ComponentScore:
        material = [t for t in transitions if t.get("is_material")]
        if not material:
            return ComponentScore(None, DEFAULT_WEIGHTS["event_evidence"], False,
                                   "no material transition on this parcel's timeline to evaluate")
        events: List[EventLike] = [
            EventLike(id=e.id, event_type=e.event_type, event_date=e.event_date,
                      to_person_id=e.to_person_id, confidence=e.confidence)
            for e in db.query(LandEvent).filter(LandEvent.parcel_id == parcel_id).all()
        ]
        matched = sum(1 for t in material if event_matcher.match(t, events).event_id is not None)
        value = matched / len(material)
        return ComponentScore(round(value, 4), DEFAULT_WEIGHTS["event_evidence"], True,
                               f"{matched}/{len(material)} material transition(s) matched to a LandEvent")

    def _identity_confidence(self, db: Session, parcel_id: int) -> ComponentScore:
        parcel_methods = [
            m[0]
            for m in db.query(ParcelIdentifierAlias.match_method)
            .filter(ParcelIdentifierAlias.parcel_id == parcel_id)
            .all()
        ]
        person_ids = [
            p[0]
            for p in db.query(Claim.person_id)
            .filter(Claim.parcel_id == parcel_id, Claim.lifecycle_status == "ACCEPTED", Claim.person_id.isnot(None))
            .distinct()
            .all()
        ]
        person_methods = (
            [
                m[0]
                for m in db.query(PersonAlias.match_method).filter(PersonAlias.person_id.in_(person_ids)).all()
            ]
            if person_ids
            else []
        )
        all_methods = parcel_methods + person_methods
        if not all_methods:
            return ComponentScore(None, DEFAULT_WEIGHTS["identity_confidence"], False,
                                   "no recorded alias resolution for this parcel yet")
        scores = [MATCH_METHOD_SCORE.get(m, 0.5) for m in all_methods]
        value = min(scores)  # the weakest link, not the average - one fuzzy hop should show up
        return ComponentScore(round(value, 4), DEFAULT_WEIGHTS["identity_confidence"], True,
                               f"weakest of {len(all_methods)} parcel/person alias resolution(s): "
                               f"{min(all_methods, key=lambda m: MATCH_METHOD_SCORE.get(m, 0.5))}")

    def _spatial_consistency(self, db: Session, parcel: Parcel, latest_area: Optional[float],
                              latest_area_unit: Optional[str]) -> ComponentScore:
        if latest_area is None:
            return ComponentScore(None, DEFAULT_WEIGHTS["spatial_consistency"], False,
                                   "no area claim on file to compare against geometry")
        khasra_norm = parcel.khasra_number_norm
        candidates = (
            db.query(GISParcel)
            .filter(
                GISParcel.source_class == "SURVEYED",
                GISParcel.state.ilike(parcel.state),
                GISParcel.district.ilike(parcel.district),
                GISParcel.tehsil.ilike(parcel.tehsil),
                GISParcel.village.ilike(parcel.village),
            )
            .all()
        )
        match = next((g for g in candidates if normalize_identifier(g.khasra_number) == khasra_norm), None)
        if match is None:
            return ComponentScore(None, DEFAULT_WEIGHTS["spatial_consistency"], False,
                                   "no surveyed geometry on file for this parcel")

        claimed_unit = (latest_area_unit or "hectare").strip().lower()
        geometry_unit = (match.area_unit or "hectare").strip().lower()
        if claimed_unit not in _FIXED_UNIT_TO_SQM or geometry_unit not in _FIXED_UNIT_TO_SQM:
            return ComponentScore(None, DEFAULT_WEIGHTS["spatial_consistency"], False,
                                   f"'{claimed_unit}'/'{geometry_unit}' has no fixed, non-regional conversion factor")

        claimed_sqm = latest_area * _FIXED_UNIT_TO_SQM[claimed_unit]
        geometry_sqm = match.area * _FIXED_UNIT_TO_SQM[geometry_unit]
        if claimed_sqm <= 0:
            return ComponentScore(None, DEFAULT_WEIGHTS["spatial_consistency"], False,
                                   "claimed area is zero or negative - cannot compute a relative difference")
        relative_diff = abs(claimed_sqm - geometry_sqm) / claimed_sqm
        value = max(0.0, 1.0 - min(1.0, relative_diff))
        return ComponentScore(round(value, 4), DEFAULT_WEIGHTS["spatial_consistency"], True,
                               f"|claimed - surveyed| / claimed = {relative_diff:.2%} (GISParcel #{match.id})")

    # -- full parcel-level score -------------------------------------------

    def score_parcel(self, db: Session, parcel_id: int) -> SufficiencyScore:
        parcel = db.query(Parcel).filter(Parcel.id == parcel_id).first()
        components: Dict[str, ComponentScore] = {
            "extraction_quality": self._extraction_quality(db, parcel_id),
            "cross_document_agreement": self._cross_document_agreement(db, parcel_id),
            "identity_confidence": self._identity_confidence(db, parcel_id),
        }

        snapshots = timeline_builder.build(db, parcel_id)
        transitions = transition_analyzer.analyze(snapshots)
        components["temporal_continuity"] = self._temporal_continuity([s.as_of_year for s in snapshots])
        components["event_evidence"] = self._event_evidence(db, parcel_id, transitions)

        latest = snapshots[-1] if snapshots else None
        if parcel is not None:
            components["spatial_consistency"] = self._spatial_consistency(
                db, parcel, latest.area if latest else None, latest.area_unit if latest else None
            )
        else:
            components["spatial_consistency"] = ComponentScore(
                None, DEFAULT_WEIGHTS["spatial_consistency"], False, "parcel not found"
            )

        return SufficiencyScore(
            scope_type="PARCEL",
            scope_id=parcel_id,
            overall_score=_combine(components),
            components=components,
        )

    def score_finding(self, db: Session, finding_id: int, parcel_id: int) -> SufficiencyScore:
        """A finding's sufficiency is its parcel's sufficiency at scoring time - see module docstring."""
        parcel_score = self.score_parcel(db, parcel_id)
        return SufficiencyScore(
            scope_type="FINDING",
            scope_id=finding_id,
            overall_score=parcel_score.overall_score,
            components=parcel_score.components,
            formula_version=parcel_score.formula_version,
        )

    # -- narrow ranking score, used only by TimelineBuilder ----------------

    def claim_ranking_score(
        self, claim: Claim, group: List[Claim], identity_confidence: Optional[float] = None
    ) -> Optional[float]:
        """3-component stand-in for the ranking use inside TimelineBuilder - see module
        docstring for why temporal_continuity/event_evidence/spatial_consistency are
        excluded here.

        `identity_confidence` is passed in rather than looked up per claim: it's a
        property of the *parcel* (the weakest alias match method used to resolve any
        claim onto it), so `TimelineBuilder` computes it once per `build()` call
        (one query) and reuses it for every candidate claim in every group, instead
        of this method re-querying it per claim.
        """
        components: Dict[str, ComponentScore] = {}

        region = getattr(claim, "evidence_region", None)
        if region is not None and region.ocr_confidence is not None:
            components["extraction_quality"] = ComponentScore(
                region.ocr_confidence, DEFAULT_WEIGHTS["extraction_quality"], True, "this claim's own OCR region"
            )
        else:
            components["extraction_quality"] = ComponentScore(
                None, DEFAULT_WEIGHTS["extraction_quality"], False, "claim has no linked evidence region"
            )

        doc_values: Dict[int, str] = {c.document_id: (c.field_value or "").strip().casefold() for c in group}
        if len(doc_values) >= 2:
            this_value = (claim.field_value or "").strip().casefold()
            agreeing = sum(1 for v in doc_values.values() if v == this_value)
            components["cross_document_agreement"] = ComponentScore(
                agreeing / len(doc_values), DEFAULT_WEIGHTS["cross_document_agreement"], True,
                f"{agreeing}/{len(doc_values)} documents in this group agree with this claim's value",
            )
        else:
            components["cross_document_agreement"] = ComponentScore(
                None, DEFAULT_WEIGHTS["cross_document_agreement"], False, "only one document in this group"
            )

        if identity_confidence is None:
            components["identity_confidence"] = ComponentScore(
                None, DEFAULT_WEIGHTS["identity_confidence"], False, "no alias resolution recorded for this parcel yet"
            )
        else:
            components["identity_confidence"] = ComponentScore(
                identity_confidence, DEFAULT_WEIGHTS["identity_confidence"], True,
                "weakest alias match method used to resolve this parcel",
            )

        return _combine(components)

    def parcel_identity_confidence(self, db: Session, parcel_id: int) -> Optional[float]:
        """The plain float form of `_identity_confidence`, for callers (TimelineBuilder)
        that just need the number once per parcel, not the full ComponentScore."""
        component = self._identity_confidence(db, parcel_id)
        return component.value if component.available else None


evidence_sufficiency_scorer = EvidenceSufficiencyScorer()
