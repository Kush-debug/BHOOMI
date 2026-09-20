"""
TransitionAnalyzer (BHUMI_FORENSICS_SPEC.md §5.4 — Phase 4).

Consecutive `ParcelStateSnapshot`s -> typed deltas ("what changed between
year X and year Y, and was it material"). Also DERIVED / computed live, for
the same reason documented in `timeline_builder.py`.

Honesty note up front, matching PHASE3_CHANGES.md's pattern: the spec's
`Transition.explained_by_event_id` field belongs to `EventMatcher`
(§5.5, Phase 5) — `LandEvent` doesn't exist in the schema yet. This module
computes `is_material` (a real, config-driven answer) but always leaves
`explained_by_event_id = None` and does not yet distinguish "unexplained"
from "not checked for an explanation" — that distinction only becomes
meaningful once Phase 5's EventMatcher exists to actually search for a
supporting document. Calling a transition "unexplained" before that search
has ever run would be a false claim of investigation that didn't happen, so
this module deliberately does not use that word; it reports `is_material`
and lets the caller (and Phase 5) draw the "unexplained" conclusion later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.timeline_builder import ParcelStateSnapshot

ENGINE_VERSION = "phase4-transitions-v1"

# Materiality thresholds — config, not literals buried in an if-statement
# (spec §5.4: "Materiality thresholds are config, not literals").
DEFAULT_AREA_TOLERANCE_PCT = 1.0  # area changes within +/-1% are treated as rounding noise
MATERIAL_IF_OWNER_CHANGES = True
MATERIAL_IF_CLASSIFICATION_CHANGES = True


@dataclass
class TransitionConfig:
    area_tolerance_pct: float = DEFAULT_AREA_TOLERANCE_PCT
    material_if_owner_changes: bool = MATERIAL_IF_OWNER_CHANGES
    material_if_classification_changes: bool = MATERIAL_IF_CLASSIFICATION_CHANGES


class TransitionAnalyzer:
    def __init__(self, config: Optional[TransitionConfig] = None):
        self.config = config or TransitionConfig()

    def analyze(self, snapshots: List[ParcelStateSnapshot]) -> List[Dict[str, Any]]:
        """snapshots must already be sorted by as_of_year (TimelineBuilder guarantees this)."""
        transitions: List[Dict[str, Any]] = []

        for prev, curr in zip(snapshots, snapshots[1:]):
            changed_predicates: List[str] = []

            ownership_changed = self._owner_changed(prev, curr)
            if ownership_changed:
                changed_predicates.append("owner_name")

            area_delta_abs, area_delta_pct = self._area_delta(prev, curr)
            area_material = area_delta_pct is not None and abs(area_delta_pct) > self.config.area_tolerance_pct
            if area_delta_abs is not None and area_delta_abs != 0:
                changed_predicates.append("area")

            classification_changed = (
                prev.classification is not None
                and curr.classification is not None
                and prev.classification.strip().lower() != curr.classification.strip().lower()
            )
            if classification_changed:
                changed_predicates.append("classification")

            is_material = (
                (ownership_changed and self.config.material_if_owner_changes)
                or area_material
                or (classification_changed and self.config.material_if_classification_changes)
            )

            transitions.append(
                {
                    "parcel_id": prev.parcel_id,
                    "from_year": prev.as_of_year,
                    "to_year": curr.as_of_year,
                    "changed_predicates": changed_predicates,
                    "ownership_delta": {
                        "from_person_id": prev.owner_person_id,
                        "to_person_id": curr.owner_person_id,
                        "from_name": prev.owner_name,
                        "to_name": curr.owner_name,
                    }
                    if ownership_changed
                    else None,
                    "area_delta_abs": area_delta_abs,
                    "area_delta_pct": area_delta_pct,
                    "area_tolerance_pct": self.config.area_tolerance_pct,
                    "classification_delta": (
                        {"from": prev.classification, "to": curr.classification}
                        if classification_changed
                        else None
                    ),
                    "is_material": is_material,
                    "explained_by_event_id": None,  # Phase 5 (EventMatcher) fills this in
                    "engine_version": ENGINE_VERSION,
                }
            )

        return transitions

    @staticmethod
    def _owner_changed(prev: ParcelStateSnapshot, curr: ParcelStateSnapshot) -> bool:
        # Prefer comparing resolved Person ids (the whole point of Phase 3's
        # identity resolution — two spellings of one name must not read as a
        # change). Fall back to raw name comparison only when a person link
        # is missing on either side, so an unresolved owner claim still gets
        # a defensible answer instead of a silent False.
        if prev.owner_person_id is not None and curr.owner_person_id is not None:
            return prev.owner_person_id != curr.owner_person_id
        if prev.owner_name is None or curr.owner_name is None:
            return False
        return prev.owner_name.strip().lower() != curr.owner_name.strip().lower()

    @staticmethod
    def _area_delta(prev: ParcelStateSnapshot, curr: ParcelStateSnapshot):
        if prev.area is None or curr.area is None:
            return None, None
        delta_abs = curr.area - prev.area
        delta_pct = (delta_abs / prev.area * 100.0) if prev.area else None
        return delta_abs, delta_pct


transition_analyzer = TransitionAnalyzer()
