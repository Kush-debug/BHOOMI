# Phase 6 — Sufficiency & Prioritisation

**Status:** implemented, not yet run. Static-only verification on my end
(`py_compile` across the whole `backend/app` and `alembic` trees + import
checks); `pytest -v tests/test_phase6_scoring.py` is what actually proves it.

**Built against your Claude Code session's Phase 5, not against my last
delivery.** Before writing any of this I pulled the actual Phase 5 files off
your machine (`finding.py`, `analysis_service.py`, `event_matcher.py`,
`contradiction_engine.py`, `event_extraction_service.py`, `findings.py`, the
updated `processing.py`/`parcels.py`/`main.py`) into my mirror and read them,
rather than working from my own guess of what Phase 5 looked like. Phase 6
extends that real code — I did not touch `analysis_service.py`,
`event_matcher.py`, `contradiction_engine.py`, or `event_extraction_service.py`
at all; those stay exactly as your session wrote and verified them.

---

## 1. What this is, per BHUMI_FORENSICS_SPEC.md §5.7 / §5.9, §9 Phase 6 gate

> Gate: **"Score breakdown visible and reproducible."**

Two questions Phase 5 left unanswered on purpose (its own changelog said so
explicitly): *"how much should we trust what we currently believe about this
parcel?"* and *"which open finding should an officer look at first?"*
`EvidenceSufficiencyScorer` answers the first, `PriorityScorer` the second,
and `InvestigationCase` is where a parcel's prioritised findings land.

New read endpoints:

```
GET /parcels/{id}/sufficiency         -- full 6-component breakdown, computed live
GET /investigation-cases?status=&band=&parcel_id=
GET /investigation-cases/{id}
```

## 2. EvidenceSufficiencyScorer — the six components, honestly

`app/services/evidence_sufficiency_scorer.py` implements exactly the spec's
§5.7 table, six components, published weights:

| Component | Weight | Computed from |
|---|---|---|
| extraction_quality | 0.20 | mean OCR confidence of EvidenceRegions backing this parcel's accepted claims |
| cross_document_agreement | 0.20 | fraction of documents agreeing, averaged over (year, predicate) groups with >=2 independent documents |
| temporal_continuity | 0.15 | fraction of consecutive snapshot-year gaps <= 5 years (configurable) |
| event_evidence | 0.25 | fraction of material transitions matched to a real LandEvent |
| identity_confidence | 0.10 | weakest parcel/person alias match method actually used (EXACT=1.0, ALIAS=0.85, FUZZY=0.5) |
| spatial_consistency | 0.10 | \|area_claimed - area_from_geometry\| / area_claimed, only when a `SURVEYED` GISParcel exists |

**Unavailable components are excluded and the remaining weights renormalised**
— never defaulted to a filler number, per spec. Every component reports
`{value, weight, available, basis}`, so "why is this score what it is" is a
stored explanation, not a black box. `formula_version` is on every score.

Two honesty notes, both flagged in the module docstring, not buried:

- **`spatial_consistency` will show `available: false` on essentially every
  parcel right now.** GIS georeferencing hasn't been built (that's Phase 10 —
  the audit already flagged `gis_parcels` geometry as invented/ungeoreferenced).
  This component's code path is real and will light up the moment a genuine
  `SURVEYED` `GISParcel` exists for a parcel; until then, reporting
  "unavailable — no surveyed geometry on file" is the honest state, exactly
  matching the worked example in spec §8: *"spatial_consistency reported as
  unavailable unless surveyed geometry is supplied."* I did not implement a
  proxy or estimated geometry to make this component "available" — that
  would be fabricating spatial data.
- **Unit conversion for `spatial_consistency` is limited to hectare/acre/
  sq_meter** — real, fixed, non-regional conversion factors. `bigha`/`biswa`
  vary by state and era with no single correct factor; comparing across them
  would mean inventing a number. If either side's area unit is bigha/biswa,
  the component reports unavailable rather than guessing a conversion.

## 3. Two scoring entry points, and why there are two

`score_parcel(db, parcel_id)` is the real, full six-component score — what's
returned by `/parcels/{id}/sufficiency` and what populates
`Finding.evidence_sufficiency`.

`claim_ranking_score(claim, group, identity_confidence)` is a **narrower
3-component** score (extraction_quality, cross_document_agreement,
identity_confidence) used only inside `TimelineBuilder` to pick the winning
claim within a (year, predicate) group — see §4. It excludes
`temporal_continuity`, `event_evidence`, and `spatial_consistency` because
those three need the timeline/transitions to already exist to be computed,
and using them to help build the timeline would be circular (the ranking
decision would depend on its own output). This is a documented, deliberate
narrowing — not a shortcut hidden from you — and it's why `TimelineBuilder`
doesn't just call `score_parcel` per candidate claim.

`score_finding` (used for `Finding.evidence_sufficiency`) is, by design,
identical to `score_parcel` for that finding's parcel. The spec's component
table describes parcel-wide signals, not a per-finding variant; inventing a
finding-specific formula the spec doesn't define would be exactly the kind
of unsupported precision the project's honesty rules forbid. If you want
findings scored more narrowly later (e.g. only the specific claims involved
in a contradiction), that's a real, separable follow-up — flagging it here
rather than pretending this version already does it.

## 4. `TimelineBuilder` now really uses evidence sufficiency

Phase 4's changelog was explicit that `Claim.confidence` was "a documented
stand-in, not the final scorer." That's now fixed: `timeline_builder.py`
ranks candidate claims within a (year, predicate) group by
`claim_ranking_score`, falling back to raw `confidence` only if *every*
candidate in a group has zero computable sufficiency (e.g. none has a
linked evidence region) — a group must still produce a deterministic
winner. `ParcelStateSnapshot` gained a new field, `snapshot_sufficiency`
(mean of the winning claims' actual ranking scores); the existing
`snapshot_confidence` field keeps its original meaning (mean raw confidence)
so nothing that already reads it changes shape.

**A note on how this was wired without a test run to catch mistakes:**
`evidence_sufficiency_scorer.py` needs `timeline_builder.py` (to reuse
`SNAPSHOT_PREDICATES` and to run `build()` when computing a parcel's full
score), and `timeline_builder.py` now needs the scorer for ranking — a
circular dependency on paper. I resolved it by making
`timeline_builder.py`'s import of the scorer a deferred (in-function) import
rather than a module-level one; I traced through Python's import mechanics
by hand (documented in both files' docstrings) rather than asserting this
works from confidence alone. I could not execute this to confirm — flagging
that plainly rather than claiming it's verified.

## 5. PriorityScorer

`app/services/priority_scorer.py`, exactly the spec §5.9 formula:

```
priority = w1*severity + w2*(1 - evidence_sufficiency) + w3*ownership_involved
         + w4*area_magnitude + w5*staleness
```

Every term is returned alongside the score (`terms: {name: {value, weight,
available, basis}}`), so ranking is explainable, not just numeric. Bands:
CRITICAL >= 0.75, HIGH >= 0.55, MEDIUM >= 0.35, else LOW — config constants,
not literals in an if-chain.

`area_magnitude` is the one term worth explaining: neither
`Finding.source_claim_ids` (empty for `EVIDENCE_GAP` — a gap isn't "from"
one claim) nor `explanation_params_json` (Phase 5's stored params are a
rendered sentence, not a raw number) carries a numeric delta to read. Rather
than adding a field to `Finding` — which would mean touching your
already-verified Phase 5 migration/model — this term recomputes the
matching transition live from the evidence layer (`from_year`/`to_year`
already on the finding identify which transition) and reads
`area_delta_pct` off it. Same "derive, don't store a duplicate" approach
Phase 4 already established for the timeline itself. For a `CONTRADICTION`
on the `area` predicate, it parses the raw values already stored in
`explanation_params_json["values"]` instead. Any other finding type/predicate
combination reports this term unavailable rather than guessing.

## 6. InvestigationCase

`app/models/investigation.py` — one row per parcel with at least one active
(`OPEN`/`IN_REVIEW`) finding, per spec §3.3's field list
(`parcel_id, finding_ids[], priority_score, priority_band, assigned_to,
status, opened_at, sla_due_at, comments[], resolution`).

**`assigned_to`/`comments`/`resolution` are declared but nothing in this
phase writes to them.** The spec's own phase table puts "Officer workflow"
(assign, comment, resolve) one phase *after* "Sufficiency & prioritisation"
— this model exists now because `PriorityScorer` needs somewhere to persist
its output, not because the workflow is built. `sla_due_at` is the one
exception: it's set once, at case-creation time, from a deterministic
per-band default (CRITICAL=3 days, HIGH=7, MEDIUM=14, LOW=30 — config, not
literals) — a real, computed commitment date, not a placeholder.

Reconciliation (`investigation_service.py`) follows the same discipline
`analysis_service.py` already established for findings: a case still fully
system-owned (status `OPEN`, unassigned) has its `finding_ids`/
`priority_score`/`priority_band` refreshed on every SCORE run, and is
removed if its parcel no longer has any active finding. The moment a case is
assigned or moved to `IN_PROGRESS`/`CLOSED`, regeneration still refreshes
the score (an officer should see current numbers) but never touches
`assigned_to`/`status`/`comments`/`resolution`/`sla_due_at`, and never
auto-closes an officer-owned case even if every finding resolves — that
closure is the officer's call, once Phase 7 gives them a way to make it.

## 7. Persisted score breakdowns

`app/models/sufficiency.py` — `EvidenceSufficiencyScore`, matching spec
§3.3's `EvidenceSufficiency` table (`scope_type {PARCEL|FINDING}, scope_id,
formula_version, components_json, overall_score, computed_at`). Upserted
(not append-only, unlike `Claim`/`OcrRun`) — a sufficiency score is a
recomputed snapshot of current belief, not a fact asserted once that must be
preserved forever; `computed_at` says how fresh it is.

One deliberate inconsistency worth flagging: `GET /parcels/{id}/sufficiency`
computes **live** rather than reading this persisted table (same choice
Phase 4 made for the timeline itself — always fresh, no staleness risk on a
read endpoint). The persisted table is written only by the SCORE pipeline
stage, for `Finding.evidence_sufficiency` linkage and as an audit trail of
what was actually used to prioritise a case at the time it was scored. If
you'd rather the GET endpoint read the cached row instead (cheaper, but can
lag behind the latest claims until the document is next reprocessed), that's
a one-line change — flagging the choice rather than deciding it's obviously
right.

## 8. Pipeline wiring

`app/api/v1/processing.py` — new **Stage: scoring (Phase 6)** immediately
after Phase 5's ANALYSE stage, same non-fatal pattern (`try/except` around
`investigation_service.score_and_prioritize_parcel`, failure logged as
`SCORING_FAILED` via the existing audit service, document still finishes).

## 9. Migration

`alembic/versions/0005_phase6_sufficiency_investigation.py` — purely
additive: `evidence_sufficiency_scores` and `investigation_cases`.
`Finding.evidence_sufficiency` already existed as a column from 0004 (NULL);
no schema change needed there, Phase 6 just starts writing to it.

## 10. Tests

`tests/test_phase6_scoring.py`, new — one corpus (owner + area change,
2008-2014, no mutation number — the same evidence-gap shape
`test_findings.py` already established) pushed through upload -> process:

| Test | Proves |
|---|---|
| `test_sufficiency_breakdown_is_complete_and_honest_about_gaps` | all 6 components present; `extraction_quality`/`identity_confidence`/`event_evidence` are real, available numbers; `spatial_consistency` is honestly `available: false` with a stated reason, never a fabricated comparison |
| `test_finding_evidence_sufficiency_is_populated_after_scoring` | `Finding.evidence_sufficiency`, NULL through Phase 5, is a real number after this phase's SCORE stage runs |
| `test_investigation_case_is_created_with_explainable_priority` | a case exists, referencing the real finding, with a priority score whose breakdown terms sum to it and whose language stays free of forbidden words |

## 11. What Phase 6 deliberately did not do

- **No officer workflow** — `assigned_to`/`comments`/`resolution` on
  `InvestigationCase` are declared and protected from being overwritten by
  regeneration, but nothing assigns, comments, or resolves yet. Phase 7.
- **`spatial_consistency` stays unavailable for every real parcel today** —
  correct behaviour until Phase 10 (GIS/geometry) exists, not a bug.
- **No `RULE_VIOLATION`/`DUPLICATE`/`SPATIAL_INCONSISTENCY` findings** —
  still just `CONTRADICTION`/`EVIDENCE_GAP` from Phase 5; the versioned
  `RuleEngine` (spec §5.8) that would produce `RULE_VIOLATION` wasn't built
  in this pass either.
- **No frontend** — reachable at `/docs` and by the tests. The Investigation
  Center queue UI is Phase 8/7 territory.
- **`temporal_continuity`'s "well-covered" threshold (5 years) is a stated
  configuration choice, not a value derived from the spec** — the spec
  describes the component conceptually ("fraction of consecutive year-gaps
  ... covered by evidence") without a precise formula; I picked a concrete,
  documented, config-driven interpretation rather than leaving it vague or
  inventing false precision. Said plainly here so it's a known judgment
  call, not a hidden one.

## 12. Run it

```bash
alembic upgrade head          # picks up 0005
pytest -v tests/test_phase6_scoring.py
# or the full suite:
pytest -v
```
