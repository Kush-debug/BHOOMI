"""
TimelineBuilder (BHUMI_FORENSICS_SPEC.md §5.3 — Phase 4).

Turns a parcel's accepted claims into an ordered series of
`ParcelStateSnapshot`s — one row per year the parcel was mentioned in any
document, holding the system's best-supported belief about that parcel's
owner/area/classification/khata number *as of that year*.

Design decision worth flagging: the spec lists `ParcelStateSnapshot` and
`Transition` as domain-model tables. They're also explicitly labelled
**DERIVED** in the same spec section, and principle #7 says reconstruction
should be "ordinary code... recomputable from the evidence layer at any
time." Phase 4 takes that literally: snapshots and transitions are computed
fresh from `claims` on every request, not persisted or cached. That avoids a
whole class of staleness bugs (a snapshot table going stale the moment a
correction supersedes a claim) for a cost that's negligible at hackathon/pilot
data volumes. If a real deployment's claim volume ever makes live
recomputation too slow, the natural fix is a cache table keyed by
`(parcel_id, engine_version)` invalidated on claim writes — not a redesign.

Phase 6 update: §5.3 says the winning claim per year/predicate should be
"the claim with the highest evidence sufficiency." `EvidenceSufficiencyScorer`
now exists (`app/services/evidence_sufficiency_scorer.py`), and its
`claim_ranking_score` — a 3-component subset (extraction_quality,
cross_document_agreement, identity_confidence) of the full published
formula — is the real ranking signal below. It's a subset, not the full six
components, because the other three (temporal_continuity, event_evidence,
spatial_consistency) each need the timeline to already exist to be computed;
using them to help build the timeline would be circular. That narrowing is
documented on `claim_ranking_score` itself, not hidden here.

`Claim.confidence` is kept as a fallback, only for the case where the
sufficiency score is itself unavailable for every candidate in a group (e.g.
none of them has a linked evidence region yet) — a group must still produce
a deterministic winner. `snapshot_confidence` keeps its Phase 4 meaning
(mean raw confidence of the winning claims); the new `snapshot_sufficiency`
field is the mean of their actual ranking scores, i.e. the real signal that
picked them.

The import of `evidence_sufficiency_scorer` is deferred to inside `build()`
rather than a module-level import: that module itself imports
`timeline_builder` (to reuse `SNAPSHOT_PREDICATES` and to run this same
`build()` when computing the full parcel-level score) — a lazy import here
breaks what would otherwise be a circular import between the two modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.ocr import Claim

ENGINE_VERSION = "phase4-timeline-v1"

# Predicates a snapshot tracks. Anything else extracted (father_name, survey
# remarks, etc.) isn't part of parcel *state* and is left out of the
# snapshot on purpose — the timeline is about what changes over time for a
# parcel, not a dump of every field ever extracted about it.
SNAPSHOT_PREDICATES = ("owner_name", "area", "land_classification", "khata_number")


@dataclass
class ParcelStateSnapshot:
    parcel_id: int
    as_of_year: int
    owner_person_id: Optional[int] = None
    owner_name: Optional[str] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    classification: Optional[str] = None
    khata_number: Optional[str] = None
    supporting_claim_ids: Dict[str, int] = field(default_factory=dict)
    contested_predicates: List[str] = field(default_factory=list)
    snapshot_confidence: Optional[float] = None
    snapshot_sufficiency: Optional[float] = None
    computed_at_engine_version: str = ENGINE_VERSION

    def as_dict(self) -> Dict[str, Any]:
        return {
            "parcel_id": self.parcel_id,
            "as_of_year": self.as_of_year,
            "owner_person_id": self.owner_person_id,
            "owner_name": self.owner_name,
            "area": self.area,
            "area_unit": self.area_unit,
            "classification": self.classification,
            "khata_number": self.khata_number,
            "supporting_claim_ids": self.supporting_claim_ids,
            "contested_predicates": self.contested_predicates,
            "snapshot_confidence": self.snapshot_confidence,
            "snapshot_sufficiency": self.snapshot_sufficiency,
            "engine_version": self.computed_at_engine_version,
        }


def _confidence_rank(claim: Claim) -> float:
    # NULL confidence (Phase 1's honest "not computable") ranks last, not as
    # zero-is-worse-than-negative — it must never beat a real score, but it
    # also must never crash the comparison. Used only as the fallback when
    # no candidate in a group has a real sufficiency score.
    return claim.confidence if claim.confidence is not None else -1.0


class TimelineBuilder:
    """Builds a parcel's timeline from its currently-accepted claims."""

    def build(self, db: Session, parcel_id: int) -> List[ParcelStateSnapshot]:
        # Deferred import — see module docstring for why this can't be a
        # top-level import (evidence_sufficiency_scorer imports this module).
        from app.services.evidence_sufficiency_scorer import evidence_sufficiency_scorer

        identity_confidence = evidence_sufficiency_scorer.parcel_identity_confidence(db, parcel_id)

        claims = (
            db.query(Claim)
            .filter(
                Claim.parcel_id == parcel_id,
                Claim.lifecycle_status == "ACCEPTED",
                Claim.standardized_field.in_(SNAPSHOT_PREDICATES + ("area_unit",)),
            )
            .join(Claim.document)
            .all()
        )
        if not claims:
            return []

        # Group by (as_of_year, predicate) using the claim's document_year —
        # the only "when does this claim describe the parcel as of" signal
        # that actually exists in the schema today. A document with no year
        # set falls back to the model default (2024, see Document.document_year)
        # rather than being silently dropped — an unknown year is still a
        # real claim that belongs somewhere on the timeline.
        by_year_predicate: Dict[tuple, List[Claim]] = {}
        area_units_by_year: Dict[int, List[Claim]] = {}
        for c in claims:
            year = c.document.document_year
            if c.standardized_field == "area_unit":
                area_units_by_year.setdefault(year, []).append(c)
                continue
            by_year_predicate.setdefault((year, c.standardized_field), []).append(c)

        years = sorted({y for (y, _p) in by_year_predicate.keys()})
        snapshots: List[ParcelStateSnapshot] = []

        for year in years:
            snap = ParcelStateSnapshot(parcel_id=parcel_id, as_of_year=year)
            confidences: List[float] = []
            sufficiencies: List[float] = []

            for predicate in SNAPSHOT_PREDICATES:
                group = by_year_predicate.get((year, predicate), [])
                if not group:
                    continue

                distinct_values = {(c.field_value or "").strip() for c in group}
                # Same year, same predicate, genuinely different values from
                # (potentially) different documents: don't silently pick a
                # winner and hide the disagreement. Still report a value (the
                # highest-sufficiency one) so the UI has something to show,
                # but flag the predicate as contested — spec §5.3.
                if len(distinct_values) > 1:
                    snap.contested_predicates.append(predicate)

                ranked = [
                    (c, evidence_sufficiency_scorer.claim_ranking_score(c, group, identity_confidence))
                    for c in group
                ]
                if any(score is not None for _c, score in ranked):
                    winner, winner_score = max(ranked, key=lambda cs: cs[1] if cs[1] is not None else -1.0)
                    sufficiencies.append(winner_score)
                else:
                    # No candidate in this group has a computable sufficiency
                    # score at all (e.g. no evidence regions, no corroboration,
                    # no identity resolution) — fall back to raw confidence so a
                    # group still produces a deterministic winner (Phase 4
                    # behaviour, unchanged for this edge case).
                    winner = max(group, key=_confidence_rank)

                if winner.confidence is not None:
                    confidences.append(winner.confidence)
                snap.supporting_claim_ids[predicate] = winner.id

                if predicate == "owner_name":
                    snap.owner_name = winner.field_value
                    snap.owner_person_id = winner.person_id
                elif predicate == "area":
                    try:
                        snap.area = float(winner.field_value) if winner.field_value else None
                    except (TypeError, ValueError):
                        snap.area = None
                elif predicate == "land_classification":
                    snap.classification = winner.field_value
                elif predicate == "khata_number":
                    snap.khata_number = winner.field_value

            unit_group = area_units_by_year.get(year)
            if unit_group:
                snap.area_unit = max(unit_group, key=_confidence_rank).field_value

            snap.snapshot_confidence = (
                sum(confidences) / len(confidences) if confidences else None
            )
            snap.snapshot_sufficiency = (
                sum(sufficiencies) / len(sufficiencies) if sufficiencies else None
            )
            snapshots.append(snap)

        return snapshots


timeline_builder = TimelineBuilder()
