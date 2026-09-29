"""
Phase 5 — EventMatcher unit tests (BHUMI_FORENSICS_SPEC.md §5.5).

Pure function, no DB, no OCR: given a transition and a list of events, does
it pick the right explanation — and, crucially, does it return *nothing*
when there is no supporting event (the EVIDENCE_GAP signal) rather than
guessing.
"""
from app.services.event_matcher import EventLike, event_matcher


def _transition(**over):
    base = {
        "from_year": 2008,
        "to_year": 2014,
        "is_material": True,
        "changed_predicates": ["owner_name"],
        "ownership_delta": {"from_person_id": 1, "to_person_id": 2, "from_name": "A", "to_name": "B"},
        "area_delta_abs": None,
        "area_delta_pct": None,
        "area_tolerance_pct": 1.0,
        "classification_delta": None,
    }
    base.update(over)
    return base


def test_mutation_in_window_with_matching_new_owner_explains_ownership_change():
    events = [EventLike(id=7, event_type="MUTATION", event_date=2011, to_person_id=2)]
    r = event_matcher.match(_transition(), events)
    assert r.event_id == 7
    assert r.match_confidence == 1.0
    assert "date_in_transition_window" in r.basis
    assert "new_owner_matches" in r.basis


def test_no_event_returns_no_match_not_a_guess():
    r = event_matcher.match(_transition(), [])
    assert r.event_id is None and r.match_confidence is None


def test_event_naming_a_different_incoming_owner_is_rejected():
    events = [EventLike(id=9, event_type="MUTATION", event_date=2011, to_person_id=999)]
    r = event_matcher.match(_transition(), events)
    assert r.event_id is None


def test_wrong_event_type_does_not_explain_area_change():
    t = _transition(changed_predicates=["area"], ownership_delta=None,
                    area_delta_abs=-0.9, area_delta_pct=-18.0)
    # A REGISTRATION doesn't cause an area change; only PARTITION / SURVEY_CORRECTION do.
    assert event_matcher.match(t, [EventLike(id=1, event_type="REGISTRATION", event_date=2011)]).event_id is None
    assert event_matcher.match(t, [EventLike(id=2, event_type="PARTITION", event_date=2011)]).event_id == 2


def test_non_material_transition_is_never_matched():
    r = event_matcher.match(_transition(is_material=False), [EventLike(id=1, event_type="MUTATION", event_date=2011, to_person_id=2)])
    assert r.event_id is None


def test_event_outside_window_is_weak_but_still_a_candidate():
    events = [EventLike(id=5, event_type="MUTATION", event_date=2020, to_person_id=2)]
    r = event_matcher.match(_transition(), events)
    assert r.event_id == 5
    assert "date_outside_window" in r.basis
    assert r.match_confidence < 1.0
