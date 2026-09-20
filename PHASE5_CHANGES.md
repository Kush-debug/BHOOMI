# Phase 5 — Event Matching + Contradiction Detection

**Status:** implemented and run. `pytest -v` → 63 passed, 1 skipped
(the 1 skip is the deliberately-superseded `test_backend.py`). Phases 1–4
unaffected.

Builds directly on Phase 4's live-computed timeline:

```
ParcelStateSnapshot → ParcelTransition → LandEvent → EventMatcher
→ explained_by_event_id → ContradictionEngine → Finding
```

---

## 1. What this answers (BHUMI_FORENSICS_SPEC.md §5.5 / §5.6, §9 Phase 5 gate)

**"What event explains this change?"** — for each *material* transition,
`EventMatcher` searches the parcel's `LandEvent`s for one that could have
caused it. Matched → `Transition.explained_by_event_id` + a match
confidence. Unmatched → an `EVIDENCE_GAP` finding with a concrete
recommended action.

**"Which changes are actually contradictory?"** — `ContradictionEngine`
finds the same parcel + same predicate + same year with incompatible values
across *independent* documents → a `CONTRADICTION` finding carrying both
source claims, both documents, and both evidence regions. Neither claim is
discarded or marked wrong.

Gate test corpus: two real PDFs pushed through `upload → process`, owner
`Ram Autar → Meera Devi` and area `4.8 → 3.9` between 2008 and 2014. With no
mutation number in either document the 2008→2014 transition is an
`EVIDENCE_GAP`; add `Mutation Number: M-4471` to the 2014 document and the
gap closes because the mutation event now explains it. Same five-line change
under a different khasra number → identical behaviour, new parcel (no
hardcoded results).

## 2. New persisted tables (migration `0004_phase5_events_findings`)

Phase 4 added no tables (snapshots/transitions are computed live). Phase 5
adds two, because both have a lifecycle that must survive recomputation:

| Table | Purpose |
|---|---|
| `land_events` | One row per event a document attests to. `event_type ∈ {MUTATION, REGISTRATION, SALE, INHERITANCE, PARTITION, CLASSIFICATION_CHANGE, SURVEY_CORRECTION}`, `event_date` (year), `order_number`, `to_person_id`, `area_after`, `evidence_claim_ids[]`, `confidence`. Keyed idempotently by `(parcel, document, event_type)`. |
| `findings` | `finding_type`, `parcel_id`, `severity`, `affected_predicates[]`, `time_range_start/end`, `source_claim_ids[]`, `source_document_ids[]`, `rule_id` + `rule_version`, `explanation_template` + `explanation_params_json` (rendered by the API so wording is auditable and can't drift), `evidence_sufficiency` (NULL — Phase 6), `recommended_action`, `resolution_status ∈ {OPEN, IN_REVIEW, RESOLVED, DISMISSED}`, `resolved_by`, `resolution_note`. Idempotent `dedupe_key`. |

Migration is additive; downgrade drops both tables cleanly. Applied to the
dev DB (`alembic current` → `0004_phase5_events_findings`).

## 3. How events are extracted (`app/services/event_extraction_service.py`)

Deterministic, from a document's own claims:

- a `mutation_number` claim → a `MUTATION` event
- a `registration_number` claim → a `REGISTRATION` event

An event is only ever created from something a document *says* (a mutation
number, grounded in OCR like any other claim). The *absence* of a mutation
number never creates anything here — that absence is exactly what
`EventMatcher` reports as an `EVIDENCE_GAP`, and only after it has searched.

**Honesty note:** `event_date` is the document's `document_year` — the
schema has no finer date signal yet (extraction doesn't pull
mutation/registration *dates*, only numbers). A matched event's date
precision is therefore "the year of the document that recorded it". Adding
date extraction is a scoped follow-up, not part of this phase.

## 4. How matching works (`app/services/event_matcher.py`)

Pure function (`EventLike` DTO, no ORM/DB — unit-tested in
`tests/test_event_matcher.py`). For a material transition:

- event type must be able to cause the observed change
  (MUTATION/REGISTRATION/SALE/INHERITANCE/PARTITION → ownership;
  PARTITION/SURVEY_CORRECTION → area; CLASSIFICATION_CHANGE → classification)
- `+0.3` if the event's year is in `[from_year, to_year]`; an event dated
  just outside stays a weak candidate (coarse yearly dating) but isn't rewarded
- `+0.2` if the event's `to_person_id` matches the transition's new owner;
  an event naming a *different* incoming owner is rejected outright
- best candidate wins; `(None, None)` when nothing matches — never a guess

## 5. How contradictions work (`app/services/contradiction_engine.py`)

Same `(parcel, predicate, year)` group, ≥2 distinct values, **≥2 distinct
documents**. A single document disagreeing with itself is an extraction bug,
not a records conflict, and is excluded. Output carries every conflicting
claim id, every document id, and every evidence region id — the
disagreement is preserved in full for an officer to reconcile.

## 6. Orchestration (`app/services/analysis_service.py`)

`analyze_parcel(db, parcel_id)` runs after RESOLVE in
`POST /processing/{id}/start` (non-fatal, like RESOLVE — a failure is
audit-logged as `ANALYSIS_FAILED` and the document still finishes):

1. extract events for every document linked to the parcel
2. build snapshots + transitions (Phase 4, live)
3. match each material transition; unmatched → desired `EVIDENCE_GAP`
4. `ContradictionEngine` → desired `CONTRADICTION`s
5. **reconcile:** insert/update findings by `dedupe_key`; delete OPEN,
   system-owned findings whose condition no longer holds; **never touch a
   finding an officer has moved to IN_REVIEW / RESOLVED / DISMISSED**
   (spec §2 rule 4 applied to the investigation layer). Reprocessing a
   document does not duplicate findings — proven by
   `test_reprocessing_does_not_duplicate_findings`.

## 7. API (BHUMI_FORENSICS_SPEC.md §6)

```
GET /findings?type=&severity=&status=&parcel_id=   -- list, severity-ordered
GET /findings/{id}                                 -- detail + parcel + source documents
GET /parcels/{id}/events                            -- LandEvents for a parcel
GET /parcels/{id}/findings                          -- findings for a parcel
GET /parcels/{id}/timeline                          -- now fills explained_by_event_id
                                                        + match_confidence on each transition
```

All `require_roles(CAN_READ_FINDINGS / CAN_READ_DOCUMENTS)` — reuses the
RBAC groups Phase 1 already defined; viewers get 403.

## 8. Language discipline (spec §2 rule 8)

Findings render from templates only. Permitted wording: *unexplained
transition, no supporting record on file, record conflict, both remain on
file, requires verification, recommended: retrieve …*. Forbidden words
(*fraud, forgery, illegal, guilty, criminal, fake*) are asserted absent from
every rendered explanation + recommended action in `test_findings.py`.
Unexplained ≠ fraud; contradiction ≠ guilt; a finding is a signal to
investigate, not a judgment.

## 9. What Phase 5 deliberately did not do

- **No date extraction** — events are dated to the document year (§3).
- **No `from_person_id` inference** — a document records the post-event
  state; its owner is the `to` party. The `from` party comes from the
  transition's previous snapshot at match time, not stored on the event.
- **No `evidence_sufficiency` on findings** — that column is present and
  NULL; `EvidenceSufficiencyScorer` is Phase 6.
- **No officer resolve/assign endpoint** — findings are read-only here;
  the Investigation Center workflow (assign, comment, resolve) is Phase 7.
  `resolution_status` already models the lifecycle the reconciler respects.
- **No frontend** — findings/events are reachable at `/docs` and by the
  tests. The Conflicts / Evidence Gaps screens are Phase 8.
- **No `SPATIAL_INCONSISTENCY` / `DUPLICATE` / `RULE_VIOLATION` findings** —
  the `finding_type` enum includes them; only `CONTRADICTION` and
  `EVIDENCE_GAP` are generated in this phase. The versioned `RuleEngine`
  (spec §5.8) that produces `RULE_VIOLATION` is a later increment.

## 10. Run it

```bash
alembic upgrade head          # picks up 0004
pytest -v tests/test_event_matcher.py tests/test_findings.py
# or the full suite:
pytest -v
```
