# BHUMI FORENSICS — Target Architecture Specification

**SIH 2026 · Problem Statement SIH26018 · Intelligent Land Record Digitization and Validation**
**Status: PROPOSED — awaiting approval. No refactoring has begun.**
**Supersedes:** nothing yet. Once approved, this becomes the project's source of truth,
subordinate only to the running implementation.
**Companion:** `ARCHITECTURE_AUDIT.md` (Phase 0 findings).

---

## 1. Product statement

> **BHUMI FORENSICS reconstructs the evidence-backed history of a land parcel across
> fragmented records, and identifies unexplained changes, conflicting records and missing
> supporting events — so officers investigate the cases that matter instead of checking
> everything by hand.**

Design principle, applied everywhere without exception:

> **AI proposes. Evidence explains. The authorised officer decides.**

The system never states that a record is fraudulent, never states that ownership is valid,
and never marks anything legally authoritative on its own.

### 1.1 What changes conceptually

| Today | Target |
|---|---|
| Document → OCR → row | Document → **evidence** → **parcel** → **history** → **finding** → investigation |
| `LandRecord` is 1:1 with a document | `Parcel` is the durable entity; documents are *evidence about* it |
| A field has a value and a number | A **claim** has a value, a source region, a method, a time it refers to, and a status |
| Validation emits warning strings | Engines emit **structured findings** with severity, time range, evidence and a recommended action |
| One "AI confidence" | **Evidence sufficiency** with a published, component-wise, configurable formula |
| Every uncertain field goes to a human | Findings are **prioritised**; humans see the cases that matter |

---

## 2. Non-negotiable engineering rules

These are enforced by tests, not by convention.

1. **No fabrication.** No code path may synthesise document content, field values, bounding
   boxes, confidences, statistics, or geometry and present them as derived from a real
   input. When a stage cannot produce a result, it fails with a typed error that reaches
   the UI.
2. **No bounding box without OCR geometry.** `EvidenceRegion.geometry_source` is one of
   `OCR_WORD_BOX | OCR_LINE_BOX | MANUAL`. If OCR gave no geometry, no region is created and
   the UI renders "no source region available for this field".
3. **No number without a computation.** Every confidence, score and metric on screen must be
   traceable to a function over stored data. A component that cannot be computed is reported
   as `unavailable`, never defaulted.
4. **Originals are immutable.** OCR runs, claims and geometry are append-only. A human
   correction creates a *new* claim that supersedes the old one; both remain queryable.
5. **Provenance is explicit.** Every document carries `source_class ∈
   {REAL_UPLOAD, SEED_SYNTHETIC, EXTERNAL_IMPORT}` and it is visible in the UI and excluded
   or segregated in metrics.
6. **Mocks are labelled.** Any integration without a live tested endpoint is a
   `MockAdapter`, returns `provider_mode: "SIMULATED"`, and the UI shows it.
7. **Deterministic where determinism is possible.** Timeline reconstruction, transition
   analysis, contradiction detection, evidence-gap detection, sufficiency scoring and
   prioritisation are ordinary code with unit tests — not model calls.
8. **Language is careful.** Permitted: *unexplained transition, record conflict, evidence
   gap, requires verification, possible missing event, low evidence sufficiency*.
   Forbidden: *fraud, forgery, illegal, verified by AI, detected by AI*.

---

## 3. Target domain model

Three layers: **evidence** (what a document says), **domain** (what we believe about a
parcel), **investigation** (what a human must do). Derived layers are recomputable from
the evidence layer at any time.

### 3.1 Evidence layer

```
Document ─┬─ source_class {REAL_UPLOAD|SEED_SYNTHETIC|EXTERNAL_IMPORT}
          ├─ sha256, file_path, mime, page_count, uploaded_by, ingest_state
          └─ DocumentPage[]  (page_no, raw_path, enhanced_path, width_px, height_px)

OcrRun ─── document_id, page_no, engine, engine_version, params_json,
           raw_text, mean_word_confidence, word_count, status, error, started/finished_at
           (append-only: reprocessing adds a run, never replaces one)

EvidenceRegion ── ocr_run_id, page_no, bbox[x,y,w,h], page_w, page_h,
                  text, ocr_confidence, geometry_source {OCR_WORD_BOX|OCR_LINE_BOX|MANUAL}

Claim ─┬─ predicate      owner_name|father_name|khasra|khata|survey|area|area_unit|
       │                 classification|mutation_no|mutation_date|registration_no|
       │                 registration_date|village|tehsil|district|state
       ├─ subject        parcel_id (nullable until resolved), raw_identifier_text
       ├─ value          value_text, value_normalized (typed), unit_normalized
       ├─ time           as_of_year   ← the year the RECORD describes, not created_at
       ├─ provenance     document_id, page_no, evidence_region_id (nullable),
       │                 source_text, extraction_method {REGEX_RULE|LLM_GROUNDED|MANUAL},
       │                 extractor_version
       ├─ confidence     extraction_confidence  (derived — see §5.7)
       └─ lifecycle      status {PROPOSED|ACCEPTED|REJECTED|SUPERSEDED},
                         asserted_by {SYSTEM|OFFICER}, officer_id,
                         supersedes_claim_id
```

`Claim` is the evidence graph's edge. Every fact on every screen is a `Claim` and can be
walked back to `EvidenceRegion → OcrRun → DocumentPage → Document`. This is what makes
"why does the system believe this?" a query rather than a promise.

### 3.2 Domain layer

```
Parcel ── parcel_key (unique, normalized), state/district/tehsil/village (FK to hierarchy),
          khasra_number_norm, khata_number_norm, status, first_seen_year, last_seen_year

ParcelIdentifierAlias ── parcel_id, raw_identifier, normalized, match_method, confidence
Person                ── canonical_name, normalized_name, phonetic_key
PersonAlias           ── person_id, raw_name, script, match_method, confidence

LandEvent ── parcel_id, event_type {MUTATION|REGISTRATION|SALE|INHERITANCE|PARTITION|
             CLASSIFICATION_CHANGE|SURVEY_CORRECTION}, event_date, order_number,
             from_person_id, to_person_id, area_before, area_after,
             evidence_claim_ids[], confidence

ParcelStateSnapshot (DERIVED) ── parcel_id, as_of_year, owner_person_id, area_normalized,
             area_unit, classification, khata_number, supporting_claim_ids[],
             snapshot_confidence, computed_at, engine_version

Transition (DERIVED) ── parcel_id, from_year, to_year, changed_predicates[],
             ownership_delta, area_delta_abs, area_delta_pct, classification_delta,
             is_material, explained_by_event_id (nullable), match_confidence
```

An **unexplained transition** is exactly:
`Transition.is_material AND Transition.explained_by_event_id IS NULL`.
No heuristic label, no special case — a database predicate.

### 3.3 Investigation layer

```
Finding ── finding_type {CONTRADICTION|EVIDENCE_GAP|RULE_VIOLATION|DUPLICATE|
                        SPATIAL_INCONSISTENCY|IDENTITY_AMBIGUITY}
           parcel_id, severity {CRITICAL|HIGH|MEDIUM|LOW},
           affected_predicates[], time_range_start, time_range_end,
           source_claim_ids[], source_document_ids[],
           rule_id, rule_version, explanation_template, explanation_params_json,
           evidence_sufficiency, recommended_action,
           resolution_status {OPEN|IN_REVIEW|RESOLVED|DISMISSED}, resolved_by, resolution_note

EvidenceSufficiency ── scope_type {PARCEL|FINDING}, scope_id, formula_version,
           components_json  { name: {value|null, weight, available: bool, basis: str} },
           overall_score, computed_at

InvestigationCase ── parcel_id, finding_ids[], priority_score, priority_band,
           assigned_to, status, opened_at, sla_due_at, comments[], resolution

OfficerAction / AuditEvent ── actor_id, action, target_type, target_id,
           before_json, after_json, reason, ip, timestamp   (append-only)

GisParcelGeometry ── parcel_id, geometry (PostGIS geometry when on Postgres; GeoJSON on SQLite),
           crs, geometry_source {SURVEYED|VECTORIZED_UNGEOREFERENCED|SYNTHETIC_DEMO},
           georeference_status, source_document_id, area_from_geometry

RuleVersion / ModelVersion ── registry rows so every finding names the code that produced it
```

### 3.4 Migration from the current schema

| Current | Becomes |
|---|---|
| `documents`, `document_pages` | kept, `+ source_class`, `+ sha256`, `+ page_count` |
| `ocr_results` | `ocr_runs` (append-only, per page) |
| `extracted_fields` | `claims` (+ `evidence_regions` where a real bbox exists) |
| `land_records` | **deprecated as a primary entity**; becomes a materialised "current verified state" view over `ParcelStateSnapshot` for the registry screen and CSV export |
| `validation_results` | `findings` |
| `gis_parcels` | `gis_parcel_geometry` + FK to `Parcel` |
| `training_corrections` | kept (fine as-is) |
| `verification_records`, `audit_logs` | merged into `audit_events` with typed targets |
| `master_locations` | dropped; validator moves onto `states/districts/tehsils/villages` |
| `master_land_registry` | kept, explicitly labelled a **mock authoritative registry** |

Alembic from the first change. Documents 6 and 7 (résumé fabrications) are deleted in a
data migration.

---

## 4. Processing architecture

```
POST /documents/upload
  → validate (ext, MIME sniff, size, page count, sha256 dedupe)
  → store original (immutable)  → Document(source_class=REAL_UPLOAD, state=UPLOADED)

POST /documents/{id}/process   → enqueue ProcessingJob → returns 202 + job_id
GET  /jobs/{job_id}            → real state machine + per-step progress + typed errors

ProcessingJob steps (each: idempotent, retryable, individually failable, logged):
  1 RENDER       PyMuPDF → every page → raw PNG
  2 ENHANCE      OpenCV → deskew + CLAHE + denoise + adaptive threshold
  3 QUALITY      measure blur/contrast/skew → quality score (a real measurement)
  4 OCR          OcrEngine.run(page) → text + word boxes + word confidences   [per page]
  5 SCRIPT       Unicode-histogram language detection over real OCR text
  6 TRANSLATE    identifier-masked translation of real OCR text               [optional]
  7 EXTRACT      rule extractor (+ optional grounded LLM extractor) → Claims
  8 RESOLVE      IdentityResolver → parcel_id / person_id on each claim
  9 RECONSTRUCT  TimelineBuilder → snapshots; TransitionAnalyzer → transitions
 10 ANALYSE      EventMatcher + ContradictionEngine + RuleEngine → Findings
 11 SCORE        EvidenceSufficiencyScorer; PriorityScorer → InvestigationCase
 12 NOTIFY       queue for the right officer
```

`FAILED` is a first-class terminal state carrying the real error
(`"OCR produced 0 characters — the page may be blank, non-textual, or unsupported"`)
and is retryable. **There is no fallback that invents content.**

**Runner:** FastAPI `BackgroundTasks` + a `processing_jobs` table for the MVP — no Redis,
no Celery, no extra infrastructure to demo. Behind a `JobRunner` interface so production
can swap in Celery/RQ without touching the steps.

---

## 5. Engines

All engines are pure functions over stored data in `app/engines/`, with no I/O and no
framework dependencies, so every one is unit-testable in isolation.

### 5.1 `OcrEngine` (interface)
`TesseractEngine` is the only implementation at MVP. Returns per-word text, bbox,
confidence, plus page dimensions. Contract: **raises** on failure. Adding `TrOCR`/a VLM
later is a new class, not a new branch. Handwriting (HTR) is a second engine behind the
same interface — declared as *planned*, not claimed, until it exists.

### 5.2 `IdentityResolver`
Raw identifier + administrative location → `Parcel`.
Normalisation: Devanagari/Indic digits → ASCII, separator canonicalisation (`127-2`→`127/2`),
whitespace, case. Exact normalized match → alias table → conservative fuzzy match that
creates an `IDENTITY_AMBIGUITY` finding rather than guessing.
Person matching: script-aware normalisation + a phonetic key + edit distance. Two spellings
of one name must not be reported as an ownership change — this distinction is the difference
between a real product and a demo.

### 5.3 `TimelineBuilder`
Claims (grouped by parcel, keyed by `as_of_year`) → ordered `ParcelStateSnapshot[]`.
Per year, per predicate: choose the claim with the highest evidence sufficiency. If two
claims from *different documents* disagree in the same year, do **not** silently pick one —
emit a `CONTRADICTION` finding and mark the snapshot predicate as contested.

### 5.4 `TransitionAnalyzer`
Consecutive snapshots → typed deltas. Area comparison happens in a canonical unit with a
configurable tolerance (default 1%, to absorb rounding in historical records, not real
change). Materiality thresholds are config, not literals.

### 5.5 `EventMatcher` — the core novelty
For each material transition, search `LandEvent`s for the parcel where:
date ∈ [from_year, to_year] · event type can produce this kind of change ·
direction matches (owner A→B vs a mutation naming A and B) · magnitude is consistent
(a partition should reduce area).

Matched → `Transition.explained_by_event_id`, with the match confidence recorded.
Unmatched → `EVIDENCE_GAP` finding with a **specific, actionable** recommendation:

> Ownership changed A → B and area changed 4.8 → 3.9 acres between 2008 and 2014 with no
> supporting mutation, partition or registration record. Recommended: retrieve mutation
> register and partition orders for Khasra 127/2, Tehsil Bilhaur, 2008–2014.

### 5.6 `ContradictionEngine`
Same parcel, same predicate, overlapping period, incompatible values across *independent*
documents → structured `CONTRADICTION` with both source claims, both documents, both
evidence regions, and the time range.

### 5.7 `EvidenceSufficiencyScorer`
Published, configurable, component-wise. Every component must be computable from stored
data — none may be a constant.

| Component | Computed from | Default weight |
|---|---|---|
| `extraction_quality` | mean OCR word confidence of the `EvidenceRegion`s backing the accepted claims | 0.20 |
| `cross_document_agreement` | fraction of independent documents agreeing on the predicate value | 0.20 |
| `temporal_continuity` | fraction of consecutive year-gaps in the timeline covered by evidence | 0.15 |
| `event_evidence` | fraction of material transitions with a document-backed matched event | 0.25 |
| `identity_confidence` | parcel/person resolution method (exact=1.0, alias, fuzzy) | 0.10 |
| `spatial_consistency` | \|area_claimed − area_from_geometry\| / area_claimed, **only when `geometry_source = SURVEYED`** | 0.10 |

**Unavailable components are excluded and the remaining weights are renormalised**, and the
API and UI both report which components were unavailable and why. A parcel with no surveyed
geometry shows *"spatial consistency: not available — no surveyed geometry on file"*,
never a number.

Formula version is stored on every score so historical scores stay interpretable.

### 5.8 `RuleEngine`
The existing tier-1/2 checks become versioned rule objects
(`rule_id, description, severity, input_predicates, predicate_fn, explanation_template,
version`), registered and individually unit-tested. Includes the fix for the
location-hierarchy false positive found in the audit.

### 5.9 `PriorityScorer`
`priority = w1·severity + w2·(1 − evidence_sufficiency) + w3·ownership_involved +
w4·area_magnitude + w5·staleness`, deterministic, with the contributing terms returned
alongside the score so the ordering is explainable. Bands: CRITICAL / HIGH / MEDIUM / LOW.

### 5.10 Where AI is used — and deliberately not used

| Task | Approach | Why |
|---|---|---|
| OCR / HTR | Real ML behind an interface | The genuine ML problem here |
| Script & language ID | Deterministic Unicode histogram | Already works, fully explainable |
| Translation | External MT + identifier masking | Correct division of labour |
| Field extraction | Rules first; **grounded** LLM second | An LLM extractor must return character spans into the OCR text; a value it cannot ground is **rejected**. That single rule is the anti-hallucination guardrail. |
| Entity resolution | Deterministic normalisation + phonetics | Must be reproducible and auditable |
| Timeline, contradictions, gaps, scoring, prioritisation | **Plain code with unit tests** | When a judge asks "is your detection just an LLM?", the answer is a deterministic algorithm and a test file |
| Investigation summary drafting | Optional single agent, RAG over *that parcel's own documents*, human-edited | The one place generation adds value without adding risk |

**Agentic design:** one `PipelineOrchestrator` that sequences steps, retries, and routes to
human gates — plus, at most, one genuinely agentic **Investigation Assistant**. No
multi-agent theatre. Multiple agents are justified by specialisation, isolation or
parallelism; a linear document pipeline has none of those, and a supervisor-worker swarm
here would be complexity a judge can correctly attack as decorative.

---

## 6. API surface

Versioned under `/api/v1`. Every route authenticated; every mutating route role-gated.

```
auth           POST /auth/login  /auth/logout  GET /auth/me
documents      POST /documents/upload | GET /documents | GET /documents/{id}
               GET /documents/{id}/file | GET /documents/{id}/pages/{n}[?enhanced]
processing     POST /documents/{id}/process → 202 | GET /jobs/{job_id} | POST /jobs/{id}/retry
evidence       GET /claims/{id} | GET /claims/{id}/evidence   ← the "why?" endpoint
               GET /documents/{id}/claims | GET /documents/{id}/regions
parcels        GET /parcels?q= | GET /parcels/{key}
               GET /parcels/{key}/timeline        ← Land Time Machine
               GET /parcels/{key}/state?as_of=YYYY
               GET /parcels/{key}/evidence-graph
               GET /parcels/{key}/transitions | /events | /findings | /sufficiency | /documents
persons        GET /persons/{id} | GET /persons/{id}/parcels
findings       GET /findings?type=&severity=&status= | GET /findings/{id}
investigations GET /investigations | POST /investigations/{id}/assign
               POST /investigations/{id}/comment | POST /investigations/{id}/resolve
verification   GET /verification/queue | GET /verification/{doc_id}
               POST /verification/{doc_id}/claims/{claim_id}/correct   ← creates superseding claim
               POST /verification/{doc_id}/submit
registry       GET /records | GET /records/{id} | GET /records/export/csv   (auth required)
gis            GET /gis/parcels | GET /gis/parcels/{id} | POST /gis/vectorize-map
integrations   GET /integrations  (adapter registry + provider_mode per adapter)
analytics      GET /analytics/overview | /analytics/throughput | /analytics/quality
audit          GET /audit/events
admin          (unchanged — already correct)
```

Cross-cutting: consistent error envelope, pagination on every list, per-role rate limits on
upload and export, structured request logging with correlation ids.

---

## 7. Screens

```
BHUMI FORENSICS
├── Command Center           real metrics only; "no data yet" where there is none
├── Document Intelligence    upload · job progress · repository · per-document evidence
├── Parcels
│   └── Parcel Intelligence  ← the flagship
│       ├── Current State
│       ├── Land Time Machine   1972 ─ 1987 ─ 1996 ─ 2008 ─ 2014 ─ 2025
│       ├── Evidence Graph      fact → claim → region → page → document
│       ├── Ownership History
│       ├── Area History
│       ├── Conflicts
│       └── Evidence Gaps
├── Investigation Center     prioritised queue · case detail · assign/resolve
├── Verification             split-screen: page image ⟷ regions ⟷ claims
├── GIS                      parcel-linked; geometry provenance labelled
├── Integrations             adapter registry, each marked LIVE or SIMULATED
├── Analytics                computed metrics only
├── Audit
└── Administration           (existing module, preserved)
```

Every screen answers: **What? · Why? · Evidence? · Action? · Audit?**

The Land Time Machine's year slider reads `GET /parcels/{key}/state?as_of=YYYY` — the
displayed state is a stored `ParcelStateSnapshot`, not a client-side interpolation.

---

## 8. Golden demo — Khasra 127/2

Per MASTER BUILD PROMPT §31, the demo anomaly must **emerge from the engine**.

Corpus: five synthetic-but-realistic documents, generated as **actual PDF/image files**, so
they pass through the same OCR the judge's upload does:

| Year | Document | Owner | Area | Event evidence |
|---|---|---|---|---|
| 1972 | Khatauni extract | A | 4.8 ac | — (baseline) |
| 1987 | Khasra B-1 | A | 4.8 ac | — (no change) |
| 1996 | Khatauni + mutation fard | B | 4.8 ac | **mutation order present** |
| 2008 | Khatauni extract | C | 3.9 ac | **nothing** ← the gap |
| 2014 | Khasra B-1 | C | 3.9 ac | — (stable) |

Stored under `backend/data/demo_corpus/` with a manifest, ingested through the **same**
`/documents/upload` → `/documents/{id}/process` path as any user file, tagged
`source_class=SEED_SYNTHETIC`, and visibly labelled in the UI.

Expected engine output, produced by logic:
- 1996 transition (A→B) — **explained** by the matched mutation order
- 2008 transition (B→C, 4.8→3.9 ac) — **unexplained** → `EVIDENCE_GAP`, severity CRITICAL
- Evidence sufficiency computed from real components, with `spatial_consistency` reported
  as *unavailable* unless surveyed geometry is supplied
- `InvestigationCase` opened and prioritised above the other findings

**Proof it is not hardcoded** — required regression tests:
1. Remove the 1996 mutation document → a **second** evidence gap appears at 1996.
2. Add a plausible 2011 partition order → the 2008 gap **closes** and sufficiency rises.
3. Feed the same five documents under a different Khasra number → identical findings, new parcel.
4. Grep test: no engine module contains a parcel-number literal.

---

## 9. Phased plan

Phases follow MASTER BUILD PROMPT §34; scope inside each phase follows the audit's
priority order. Every phase ends with tests + a written note of what remains incomplete.

| Phase | Deliverable | Gate |
|---|---|---|
| **0 · Audit** | `ARCHITECTURE_AUDIT.md`, this spec | ✅ complete — **awaiting your approval** |
| **1 · Honesty & safety** | git init; delete `HybridIndicOCREngine`; typed OCR failures; RBAC on all domain routes; env-based secrets + CORS; remove hardcoded dashboard/report/verification literals; purge contaminated rows 6–7; `.env.example`; Alembic baseline | Uploading a résumé returns an explicit processing failure. `pytest` proves it. |
| **2 · Evidence foundation** | Alembic migrations; `ocr_runs`, `evidence_regions`, `claims`; real per-word boxes + real confidences; claim supersession; provenance flags | A field on screen resolves to a real highlighted region, or honestly says it has none. |
| **3 · Parcel identity** | `Parcel`, aliases, `Person`, `IdentityResolver`; claims linked to parcels; parcel search | Two documents about one Khasra converge on one parcel. |
| **4 · Reconstruction** | `TimelineBuilder`, `ParcelStateSnapshot`, `TransitionAnalyzer`; `/parcels/{key}/timeline` | Timeline API returns real snapshots from real claims. |
| **5 · Detection** | `LandEvent`, `EventMatcher`, `ContradictionEngine`, versioned `RuleEngine`, `Finding` | Golden-demo tests 1–4 pass. |
| **6 · Sufficiency & prioritisation** | `EvidenceSufficiencyScorer` (+ unavailable-component handling), `PriorityScorer`, `InvestigationCase` | Score breakdown visible and reproducible. |
| **7 · Officer workflow** | Investigation Center; evidence-linked verification; corrections as superseding claims; full audit | End-to-end golden flow runs. |
| **8 · Parcel Intelligence UI** | Parcel page, Land Time Machine, Evidence Graph, Conflicts, Gaps | A judge understands the product in 60 seconds. |
| **9 · Async pipeline** | `ProcessingJob` state machine, all pages OCR'd, retry, progress | 20-page PDF processes without a timeout. |
| **10 · GIS & integrations** | Parcel↔geometry link, geometry provenance labels, LRMS/DILRMP adapter interfaces + labelled mocks | No unlabelled simulation anywhere. |
| **11 · Analytics & Command Center** | Computed metrics; `Reports.jsx` rebuilt or removed | No number on screen without a query behind it. |
| **12 · Hardening** | Test coverage on all engines, security pass, perf, docs, `SIH_EVALUATOR_AUDIT.md` | Hostile-evaluator review passes. |

**Phase 1 is not optional and not deferrable.** Every later phase built on the current OCR
layer would be built on fabricated inputs.

---

## 10. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **A judge uploads a random PDF during Q&A** | Project credibility destroyed | Phase 1, first |
| **No git history before a large refactor** | No rollback | `git init` + branch as the very first action |
| Tesseract accuracy on Devanagari/handwriting is genuinely poor | Honest metrics look weak | Report real numbers; position human-in-the-loop as the designed answer; evaluate on a small labelled set and publish it |
| Real historical land documents are hard to source | Demo may look synthetic | Clearly labelled synthetic corpus + invite judges to upload their own; honesty is the stronger position |
| Scope is large for the remaining time | Incomplete build | Priority order is fixed: 1→2→3→4→5→6→7→8; a shippable product exists after each |
| Judges ask "is this just ChatGPT?" | Novelty challenged | Detection is deterministic and unit-tested; show the test file |
| PostGIS deployed but unused | "Why is it there?" | Either use it in phase 10 or remove it from compose |
| No execution environment in this session | Cannot verify builds/tests | Either enable a shell on your machine, or you run the commands I provide and paste the output |

---

## 11. Explicit deviations from PRD.md

The PRD remains authoritative for baseline SIH26018 requirements. This spec proposes four
deliberate changes, each with a reason:

1. **`LandRecord` is demoted from primary entity to a materialised view.** The PRD's
   document-centric model cannot express parcel history, which is the differentiator. The
   registry screen and CSV export are preserved unchanged in behaviour.
2. **`ValidationAnomaly` is generalised into `Finding`.** Contradictions and evidence gaps
   are not validation failures of a single document; they are properties of a parcel's
   history over time.
3. **Confidence is split.** PRD §9's field-level confidence bands are kept for extraction;
   `EvidenceSufficiency` is added as a separate, parcel-level, component-wise score. The two
   are never conflated in the UI.
4. **Processing becomes asynchronous.** PRD §20's state machine is implemented as a real job
   table rather than inferred from row existence, because the synchronous version cannot
   survive multi-page scans.

No PRD requirement is dropped.
