# Phase 4 — Reconstruction (Timeline)

**Status:** implemented, not yet run. Static-only verification on my end
(`py_compile` + import/dead-code checks, same as Phases 2 and 3);
`pytest -v tests/test_timeline.py` is what actually proves it.

**Division of labor note:** one new test file
(`tests/test_timeline.py`), nothing in `conftest.py` touched.

---

## 1. What this is, per BHUMI_FORENSICS_SPEC.md §5.3 / §5.4, §9 Phase 4 gate

> Gate: **"Timeline API returns real snapshots from real claims."**

Phase 3 gave every claim a durable `parcel_id`. Phase 4 is the first thing
that actually *reads* that link for something a user would look at: for a
given parcel, reconstruct what the system believed about it, year by year,
from the claims that mention it — a `ParcelStateSnapshot` per year — and
compute the deltas between consecutive years — a `Transition`.

New endpoint:

```
GET /parcels/{id}/timeline
```

Returns the parcel summary, an ordered list of snapshots, and the list of
transitions between them.

## 2. A design decision I made without asking, and why

The spec (§3.2) lists `ParcelStateSnapshot` and `Transition` as domain-model
tables, with columns like `computed_at`. The same spec section labels both
**DERIVED**, and principle #7 says reconstruction should be "ordinary
code... recomputable from the evidence layer at any time."

I took that literally: **Phase 4 adds no new database tables and no
migration.** `TimelineBuilder` and `TransitionAnalyzer`
(`app/services/timeline_builder.py`, `app/services/transition_analyzer.py`)
compute snapshots and transitions live, on every call to
`/parcels/{id}/timeline`, straight from `claims`. Nothing is cached or
persisted.

Why: a persisted snapshot table is a cache, and caches go stale. The
specific failure mode I wanted to avoid — an officer supersedes a claim with
a correction (Phase 2's whole point), and the cached snapshot table doesn't
know that happened until something remembers to recompute it — is exactly
the kind of silent-lie bug this project has spent three phases removing. At
current and realistic near-term data volumes (a few hundred claims per
parcel, at most), recomputing on every request costs single-digit
milliseconds. If a real deployment's volume ever makes that too slow, the
fix is a cache table keyed by `(parcel_id, engine_version)` that gets
invalidated when a claim affecting that parcel changes — a targeted
addition, not a redesign, and I'd rather add it when there's a real
performance number motivating it than build it speculatively now.

If you want it built as literal persisted tables instead — e.g. because a
demo needs to show "history was computed once and stored," or because the
frontend team wants to query historical computed_at timestamps — say so and
I'll add the tables; this is a reversible choice, not a foundational one.

## 3. How snapshot construction actually works

`TimelineBuilder.build(db, parcel_id)`:

1. Pulls every currently-`ACCEPTED` claim linked to the parcel whose
   `standardized_field` is one of `owner_name`, `area`, `land_classification`,
   `khata_number` (plus `area_unit` for display).
2. Groups them by `(document_year, standardized_field)` — the document's
   `document_year` is the only "as of when does this claim describe the
   parcel" signal that exists in the schema today, so that's what a
   snapshot year means in this phase.
3. Within each `(year, predicate)` group, picks the claim with the highest
   `confidence` as the winning value for that predicate that year.
4. If that group actually contains **more than one distinct value** — i.e.
   two documents disagree about the same predicate in the same year — the
   predicate is added to `contested_predicates` on the snapshot instead of
   silently picking a winner and hiding the disagreement (spec §5.3).

**Honesty note on step 3:** the spec says the winner should be "the claim
with the highest evidence sufficiency." `EvidenceSufficiencyScorer` is
Phase 6 — it doesn't exist yet. Until it does, `Claim.confidence` (a real,
non-fabricated value since Phase 1/2) is the stand-in ranking signal. This
is flagged in the module docstring, not hidden: `snapshot_confidence` on
each snapshot is honestly "the confidence of the claim that won," not a
computed sufficiency score.

## 4. How transitions work

`TransitionAnalyzer.analyze(snapshots)` walks consecutive snapshot pairs and
computes:

- `ownership_delta` — compares resolved `Person` ids first (the actual
  payoff of Phase 3's identity resolution: two spellings of one name must
  not read as an ownership change), falling back to raw name comparison
  only if a person link is missing on either side.
- `area_delta_abs` / `area_delta_pct` — with a **configurable** tolerance
  (`TransitionConfig.area_tolerance_pct`, default 1%) so rounding in
  historical records doesn't register as a real change. Config, not a
  literal buried in an if-statement, per spec §5.4.
- `classification_delta`.
- `is_material` — true if ownership changed, or the area delta exceeds
  tolerance, or classification changed. Each of those three triggers is
  also a `TransitionConfig` flag, not hardcoded logic.

**`explained_by_event_id` is always `None` in this phase, on purpose.** That
field belongs to Phase 5's `EventMatcher`, which doesn't exist yet — there's
no `LandEvent` table to search. Calling a transition "unexplained" before
anything has actually searched for a supporting mutation/partition record
would be claiming an investigation that never ran. This module reports
`is_material` (a real, computed answer) and deliberately avoids the word
"unexplained" anywhere in its output — that conclusion is Phase 5's to draw,
once `EventMatcher` exists to have actually looked.

## 5. Test

`tests/test_timeline.py`, new — two real PDFs, years apart (2008/2014), same
khasra number, with a genuine ownership change (Ram Autar -> Meera Devi) and
area change (4.8 -> 3.9) between them:

| Test | Proves |
|---|---|
| `test_timeline_returns_real_snapshots_and_a_material_transition` | two documents four years apart produce two real snapshots (each with non-empty `supporting_claim_ids` pointing at real claim ids) and exactly one transition, correctly flagged `is_material=True` with both `owner_name` and `area` in `changed_predicates`; `explained_by_event_id` stays `None` |
| `test_timeline_of_nonexistent_parcel_is_404` | the endpoint doesn't silently return an empty timeline for a parcel id that doesn't exist |

## 6. What Phase 4 deliberately did not do

- No `LandEvent`, no `EventMatcher`, no "unexplained transition" label —
  that's Phase 5, and it's what actually consumes `Transition.is_material`
  for something meaningful (searching for a supporting mutation/partition
  record and flagging what it can't find).
- No `ContradictionEngine` as a structured `Finding` — `contested_predicates`
  on a snapshot is the honest, narrower thing this phase can do without that
  model existing yet (also Phase 5).
- No persisted snapshot/transition tables — see §2.
- No frontend "Land Time Machine" — that's Phase 8; `/parcels/{id}/timeline`
  is reachable at `/docs` and by the tests, not from the UI yet.
- `village_id`-based resolution (deferred since Phase 3) is still deferred —
  a snapshot's parcel identity is only as good as Phase 3's free-text
  location matching.

## 7. Run it

No new migration, no new setup. Just:

```bash
pytest -v tests/test_timeline.py
```

(or the full `pytest -v` — Phases 1-3 logic wasn't touched, this phase only
added two new stateless services and one new GET route on the existing
`parcels` router).
