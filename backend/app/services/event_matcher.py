"""
EventMatcher (BHUMI_FORENSICS_SPEC.md §5.5 — Phase 5).

"What event explains this change?"

For one material `Transition`, search the parcel's `LandEvent`s for one that
could plausibly have caused it:

  - the event's date falls in the transition's [from_year, to_year] window
  - the event type can produce this kind of change (a MUTATION/SALE/
    INHERITANCE/REGISTRATION explains an ownership change; a PARTITION or
    SURVEY_CORRECTION explains an area change; a CLASSIFICATION_CHANGE
    explains a classification change)
  - direction is consistent (the event's `to_person_id` matches the
    transition's new owner)

Deterministic. No model call. Returns the best candidate's id and a match
confidence built from which of the above actually held — or `(None, None)`
when nothing matches, which is the signal `analysis_service` turns into an
EVIDENCE_GAP finding. An unmatched material transition is "no supporting
record on file", never "fraud".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.models.finding import (
    EVENT_CLASSIFICATION_CHANGE,
    EVENT_INHERITANCE,
    EVENT_MUTATION,
    EVENT_PARTITION,
    EVENT_REGISTRATION,
    EVENT_SALE,
    EVENT_SURVEY_CORRECTION,
)

_OWNERSHIP_EVENTS = {EVENT_MUTATION, EVENT_REGISTRATION, EVENT_SALE, EVENT_INHERITANCE, EVENT_PARTITION}
_AREA_EVENTS = {EVENT_PARTITION, EVENT_SURVEY_CORRECTION}
_CLASSIFICATION_EVENTS = {EVENT_CLASSIFICATION_CHANGE}


@dataclass(frozen=True)
class EventLike:
    """The subset of LandEvent this matcher needs — lets it be unit-tested
    without the ORM or a database."""

    id: int
    event_type: str
    event_date: Optional[int]
    to_person_id: Optional[int] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class MatchResult:
    event_id: Optional[int]
    match_confidence: Optional[float]
    basis: List[str]


def _predicate_event_types(changed_predicates: List[str]) -> set:
    wanted: set = set()
    if "owner_name" in changed_predicates:
        wanted |= _OWNERSHIP_EVENTS
    if "area" in changed_predicates:
        wanted |= _AREA_EVENTS
    if "classification" in changed_predicates:
        wanted |= _CLASSIFICATION_EVENTS
    return wanted


class EventMatcher:
    def match(self, transition: Dict[str, Any], events: List[EventLike]) -> MatchResult:
        if not transition.get("is_material") or not events:
            return MatchResult(None, None, [])

        from_year = transition["from_year"]
        to_year = transition["to_year"]
        changed = transition.get("changed_predicates", [])
        wanted_types = _predicate_event_types(changed)
        if not wanted_types:
            return MatchResult(None, None, [])

        target_owner = None
        if transition.get("ownership_delta"):
            target_owner = transition["ownership_delta"].get("to_person_id")

        best: Optional[MatchResult] = None
        for ev in events:
            if ev.event_type not in wanted_types:
                continue

            basis = ["event_type_can_cause_change"]
            score = 0.5

            in_window = ev.event_date is not None and from_year <= ev.event_date <= to_year
            if in_window:
                score += 0.3
                basis.append("date_in_transition_window")
            elif ev.event_date is not None:
                # An event dated outside the window is weak evidence, not none —
                # coarse yearly dating means an off-by-one is common. Keep it a
                # candidate but don't reward it.
                basis.append("date_outside_window")

            if target_owner is not None and ev.to_person_id is not None:
                if ev.to_person_id == target_owner:
                    score += 0.2
                    basis.append("new_owner_matches")
                else:
                    # Names a different incoming owner — actively inconsistent.
                    continue

            score = min(1.0, round(score, 4))
            candidate = MatchResult(ev.id, score, basis)
            if best is None or candidate.match_confidence > best.match_confidence:
                best = candidate

        return best or MatchResult(None, None, [])


event_matcher = EventMatcher()
