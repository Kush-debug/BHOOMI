# ARCHITECTURE AUDIT — `land-record-system` → BHUMI FORENSICS

**Audited repository:** `Downloads/land-record-system-fixed/land-record-system`
**Audit date:** 2026-09-03
**Auditor:** AI CTO / Principal Architect engagement
**Method:** full static read of 97 source files (backend 100%, frontend 100%), plus forensic
inspection of the live SQLite database `backend/bhoomi_land_records.db` and a controlled
re-execution of the OCR fallback path.
**Status:** Phase 0 complete. **No application code has been modified.**

---

## 0. Verification limits — read this first

I could not execute the application during this audit. This container has no access to
PyPI or npm (both return 403), and there is no shell on your machine from this session.
So:

| Claim type | Basis |
|---|---|
| Code behaviour | Static reading of the full source. High confidence. |
| Runtime behaviour | **Forensic**: the committed SQLite DB contains the real output of past runs. |
| OCR fallback fabrication | **Reproduced**: I executed `HybridIndicOCREngine` directly with stubbed imports. |
| Test suite passes/fails | **Not verified.** I read the tests; I did not run them. |
| Frontend build | **Not verified.** |

Nothing in this document is asserted as "tested" unless the evidence column says so.

---

## 1. Current architecture

```
frontend/  React 18 + Vite 5 + Tailwind 3 + react-router 6 + Leaflet + Recharts + axios
           15 pages, 7 shared components, 2 contexts (Auth, Language), 1 axios client
           No tests. No TypeScript. No state library (local useState + direct api calls).

backend/   FastAPI + SQLAlchemy 2 (sync) + Pydantic v2 + python-jose + bcrypt
           13 routers under /api/v1, 45 endpoints
           14 "services", 2 utils, 19 ORM tables
           SQLite by default; Postgres/PostGIS via DATABASE_URL in docker-compose
           Base.metadata.create_all() at import — no migration tool
           seed_all_data() runs on every startup

deploy/    docker-compose: postgis:16-3.4 + backend + frontend(nginx)
           start.sh (bash, references backend/venv which does not exist in this checkout)
```

**Actual request flow that exists today:**

```
Login ──JWT──> Upload (multipart) ──> save file ──> PyMuPDF render pages ──> OpenCV enhance
   ──> POST /processing/{id}/start  [SYNCHRONOUS, inside the HTTP request]
        ├─ OCR              (Tesseract, or fabricating fallback)
        ├─ Language detect  (Unicode script ranges)
        ├─ Full-text translate (deep-translator → Google Translate)
        ├─ Field extraction (regex over terminology dictionary)
        ├─ Confidence       (weighted mean of per-field constants)
        └─ Validation       (4 tiers against MasterLandRegistry / MasterLocation)
   ──> Verification queue ──> Workspace ──> submit(approve|edit|reject)
   ──> LandRecord (1 per document) ──> Registry search / CSV / GIS status sync ──> Audit
```

**Missing entirely from the flow:** any concept of a *parcel* that outlives a single
document. `LandRecord` is 1:1 with `Document`. Two Khatauni extracts for the same Khasra
across two decades produce two unrelated rows with no link between them.

---

## 2. Current data model

19 tables. Grouped by what they actually do:

| Group | Tables | Assessment |
|---|---|---|
| Identity | `users` | Solid. bcrypt hashes, role column, active flag. |
| Geography master | `countries` `states` `districts` `tehsils` `villages` | Genuinely good. 36 states/UTs, cascading FK hierarchy, indexed. Keep as-is. |
| Legacy geography | `master_locations` | Duplicate of the above, flat. Used by the validator. Redundant. |
| Documents | `documents` `document_pages` | Reasonable shape. Confidence columns have misleading defaults (see §4.4). |
| Extraction | `ocr_results` `extracted_fields` | Right idea, wrong lifecycle — overwritten on every reprocess (`DELETE` then re-insert). No history. |
| Records | `land_records` | **Document-centric, not parcel-centric.** This is the structural blocker. |
| Validation | `validation_results` `master_land_registry` | Findings are flat warning rows, not structured conflict objects. |
| GIS | `gis_parcels` | GeoJSON in a plain `JSON` column. **PostGIS is deployed but never used** — no `geometry` type, no spatial index, no spatial query anywhere. |
| Audit / HITL | `audit_logs` `notifications` `training_corrections` `verification_records` | Correct instincts. Append-only, previous/new state captured. Keep. |

**Structural gaps against the target product:** no `Parcel`, no `Person`, no `LandEvent`,
no `EvidenceRegion`, no timeline, no transition, no conflict object, no evidence-sufficiency
record, no investigation case, no model/rule versioning, no data-provenance class
(real vs seed vs synthetic).

---

## 3. What genuinely works and must be preserved

This repository is not a shell. Roughly 40% of it is real, competent work.

| # | Component | File | Why it's real |
|---|---|---|---|
| 1 | **JWT auth + bcrypt** | `auth/jwt.py`, `api/v1/auth.py` | Proper hashing, 72-byte truncation handled, real token issue/decode, login audited. |
| 2 | **Admin module + RBAC** | `api/v1/admin.py`, `auth/rbac.py` | The best-engineered module in the repo. Role hierarchy, super-admin escalation guard, uniqueness checks, deactivation, password reset — all with `require_roles` and audit events. |
| 3 | **Geography master data** | `models/location.py`, `database/seed_data.py`, `api/v1/locations.py` | 36 states/UTs + real district→tehsil→village hierarchy with cascading endpoints. Non-trivial and correct. |
| 4 | **Real PDF rendering** | `services/document_service.py` | PyMuPDF at 2.5× matrix, **every** page, saved to disk. Comment in the file records that this replaced an earlier synthetic-canvas fake. Correct fix. |
| 5 | **OpenCV preprocessing** | `utils/opencv_utils.py::preprocess_image_for_ocr` | Genuine: grayscale → CLAHE → Gaussian → adaptive threshold, writes a real enhanced image. |
| 6 | **Language detection** | `services/language_detection_service.py` | Genuinely works. Unicode block histogram over 12 Indic scripts + Latin, Marathi/Hindi disambiguation via lexical markers. Deterministic, testable, honest. |
| 7 | **Translation w/ identifier protection** | `services/translation_service.py` | Real: masks `123/4`, `UP-REG-2023-7819`, dates via regex → translates → restores. Uses deep-translator. Falls back to original text rather than destroying OCR. This is the correct design. |
| 8 | **Terminology dictionary** | `utils/terminology.py` | 14 canonical fields with multilingual regex + state overlays (UP/MP/Bihar/MH/RJ/PB/KA). Configurable, not hardcoded per-extractor. Genuinely useful IP. |
| 9 | **Validation engine (tiers 1–4)** | `services/validation_service.py`, `duplicate_service.py` | Real DB-backed rules: positive area, mandatory identifiers, location hierarchy, cross-registry area/owner comparison, weighted duplicate scoring (45/25/30/15). Structured dicts, not UI strings. |
| 10 | **Audit + HITL correction capture** | `audit_service.py`, `learning_service.py`, `verification.py` | Every correction stored with original value, corrected value, bbox, verifier, notes. Previous/new state snapshots. Append-only. |
| 11 | **Frontend shell** | `App.jsx`, `services/api.js`, `layouts/`, `components/common/` | Clean routing, protected routes, role-gated admin route, axios interceptors with 401 handling, i18n context (en/hi), restrained government-style Tailwind design. Usable foundation. |
| 12 | **Frontend is API-driven** | 13 of 15 pages | Only `Reports.jsx` and `Settings.jsx` have zero API calls. The rest genuinely fetch from the backend. |

---

## 4. Critical problems

Ordered by damage. P0 items are disqualifying in front of an SIH panel.

### 4.1 — P0 · The OCR engine fabricates land records from arbitrary files

`backend/app/services/ocr_service.py`

`OCRService.process_image()` tries Tesseract, and on **any** of: import failure, missing
binary, exception, or fewer than 20 characters of output — silently falls through to
`HybridIndicOCREngine`. That class never opens the image. It branches on the *upload form
metadata* (`state`, `district`, `language`) and returns a hand-written land record with
hand-written bounding boxes and hand-written confidences of 0.94–0.99.

**Reproduced in this audit.** I loaded the class directly and called it:

```
INPUT: /tmp/does_not_exist.png                 (file does not exist)
  engine: "Hybrid Indic OCR (Indic + Tesseract Native)"   average_confidence: 0.96
  raw_text: खसरा (प्रपत्र बी-1 / किस्तवार) - भू-अभिलेख विभाग
            खसरा संख्या / गाटा सं.: 451 | खातेदार का नाम: सुरेश कुमार ...

INPUT: data/uploads/doc_475788_Varun_Yadav_Resume (1).pdf   (a résumé)
  engine: "Hybrid Indic OCR (Indic + Tesseract Native)"   average_confidence: 0.98
  raw_text: REVENUE DEPARTMENT - GOVERNMENT OF INDIA / STATE OF UTTAR PRADESH
            CERTIFIED EXTRACT OF RECORD OF RIGHTS & CADASTRAL PARCEL ...
```

**This has already happened in your live database.** `bhoomi_land_records.db` contains:

| id | file_name | status | detected_lang | ocr_conf | stored "OCR" text |
|---|---|---|---|---|---|
| 6 | `Varun_Yadav_Resume (1).pdf` | verification_pending | hi | 0.96 | Hindi Khasra B-1 form for Gaya/Sherghati/Dobhi |
| 7 | `Varun_Yadav_Resume (1).pdf` | **processed** | ta | 0.96 | Tamil Patta/Chitta extract |

Document 7's stored extracted fields, all marked `auto_extracted`:

```
owner_name          = Ramasamy            conf=0.96   bbox {"x":50,"y":180,"w":320,"h":35}
father_name         = Murugan             conf=0.94   bbox {"x":400,"y":180,...}
khasra_number       = 123/4               conf=0.98
khata_number        = 842                 conf=0.98
area                = 0.8500              conf=0.96
registration_number = TN-REG-2023-4512    conf=0.94
```

A résumé was ingested and the system produced a named landowner, a survey number, an
area, a registration deed number, and pixel bounding boxes — none of which exist anywhere
in that file — and marked the document `processed` with `validation_status = valid`.

This violates PRD §5.1, PRD §34.7–34.9, and MASTER BUILD PROMPT §33 simultaneously. If a
judge uploads any document during Q&A, this is what they will see. **It is the single
highest-priority item in the entire project.**

### 4.2 — P0 · The test suite passes *because of* the fabrication

`backend/tests/test_backend.py::test_automatic_multilingual_ocr_and_identifier_protection`
runs the pipeline on seeded document 2, whose `file_path` is
`/app/data/demo_documents/TN_Coimbatore_Pollachi_Patta_842.pdf` — a file that does not
exist in the repository. Tesseract therefore fails, the fabricating fallback fires, and the
test asserts on the fabricated Tamil text (`ராமசாமி`, `123/4`).

The suite's headline OCR test is green only because OCR is faked. There is no test at all
for the PRD's stated critical acceptance case: *"upload a previously unseen document
containing values not present in demo data."*

### 4.3 — P0 · 30 of 45 endpoints have no authentication

| Protection | Count | Endpoints |
|---|---|---|
| RBAC (`require_roles`) | 8 | all of `/admin/*` |
| Authenticated only | 7 | upload, delete doc, processing start/translate, verification submit, notifications list, /auth/me, logout |
| **Public** | **30** | everything else |

Unauthenticated and therefore world-readable/writable when deployed:

- `GET /documents/{id}/file` — download any uploaded scan
- `GET /documents/{id}/page/{n}` — any rendered page image
- `GET /records/` and `GET /records/export/csv` — **bulk export of the entire land registry**
- `GET /audit/logs` — the security audit trail
- `PUT /validation/resolve/{id}` — **anyone can silently clear a detected anomaly**
- `PUT /notifications/read-all`
- `POST /gis/vectorize-map` — unauthenticated file upload
- `GET /dashboard/stats`, `/verification/queue`, `/learning/corrections`, `/gis/*`, `/locations/*`

Additionally, `POST /verification/{id}/submit` requires only *a* token — a `viewer`
account can approve a land record into the verified registry. RBAC exists and is used
correctly in `admin.py`; it was simply never applied to the domain routes.

### 4.4 — P0 · Fabricated numbers presented as measurements

| Location | Fabrication |
|---|---|
| `api/v1/dashboard.py` | `total_documents: 25430`, `verified: 21430`, `pending: 1690` returned whenever the real count is 0. `confidence_distribution` and `processing_timeline` are **always** hardcoded — 7 days of invented upload/process/verify counts. `state_progress` falls back to invented UP/MP/Bihar/MH totals. |
| `pages/Reports.jsx` | "OCR Accuracy by Indic Language: Hindi 96.2% (18,450 docs), English 98.4%, Mixed 93.1%". "Accuracy by Document Type: Khasra B1 97.1%…". Zero API calls. No evaluation ever ran. |
| `extraction_service.py` | `_estimate_confidence_for_field` returns literals: 0.98 if the identifier matches `^[0-9/\-]+$`, 0.96 for any owner name ≥2 chars, 0.94 otherwise. Never reads the OCR word confidence. |
| `processing.py` | `doc.validation_confidence = 0.96` — assigned unconditionally after validation. |
| `models/document.py` | Column defaults `language_confidence=0.95`, `translation_confidence=0.94`, `validation_confidence=0.95` — an unprocessed row already reports 95% confidence. |
| `translation_service.py` | Returns `confidence: 0.90` for every successful Google Translate call. |
| `cadastral_map_service.py` | `confidence: 0.94` per detected polygon. |
| `Sidebar.jsx` | "13+ Indic Languages Online" with a pulsing green status dot. Tesseract packages installed: 5. |

MASTER BUILD PROMPT §25 and §33 both prohibit this explicitly.

### 4.5 — P0 · The flagship demo anomaly is hardcoded, not computed

`seed_data.py` inserts a `ValidationResult` on document 1 with
`rule_name = "MASTER_REGISTRY_AREA_MATCH"`. **That rule name does not exist in
`validation_service.py`** — the engine emits `RULE_CROSS_DB_AREA_MISMATCH`. Confirmed in
the live database:

```
doc1  MASTER_REGISTRY_AREA_MATCH        error    (seeded literal — no engine produced it)
doc2  RULE_CROSS_DB_OWNER_MISMATCH      warning  (engine-produced)
doc6  RULE_AREA_POSITIVE                error    (engine-produced)
doc6  RULE_LOCATION_HIERARCHY_MISMATCH  error    (engine-produced — and wrong, see 4.9)
```

The demo's centrepiece finding is a literal. MASTER BUILD PROMPT §31 names this exact
anti-pattern as the thing that must not happen.

### 4.6 — P1 · Fake bounding boxes presented as OCR evidence

`extraction_service._find_bounding_box_for_text()` returns `{"x":60,"y":200,"w":250,"h":35}`
whenever it cannot match the value to an OCR block. `opencv_utils.detect_table_grid_and_stamps()`
returns three boxes computed as fixed *percentages of the image dimensions* — labelled
`header_metadata`, `table_region`, `official_stamp_signature` with confidences 0.98/0.96/0.92
— with no contour detection of any kind, despite the README claiming "morphological contour
detection". `seed_data` writes `{"x":50,"y":140,"w":300,"h":35}` for every seeded field.

The Evidence Viewer will therefore highlight a rectangle that has no relationship to the
text. MASTER BUILD PROMPT §16: *"Do not fake coordinates and pretend they came from OCR."*

### 4.7 — P1 · Hardcoded fallback values written into verified records

`api/v1/verification.py`:

```python
khasra_no = str(new_state.get("khasra_number", "456"))
khata_no  = str(new_state.get("khata_number",  "142"))
owner_str = str(new_state.get("owner_name",   "राम प्रसाद"))
```

If extraction found no owner, the approved, verified, registry-published record silently
becomes "राम प्रसाद, Khasra 456". Fabricated data entering the authoritative registry via
the human-approval path.

### 4.8 — P1 · Credentials hardcoded in the frontend

`Login.jsx` ships a `DEMO_PRESETS` array with six username/password pairs in plain text,
and `password` state is pre-initialised to `'officer123'`. `AuthContext.switchRole()`
carries a second copy of the same password map. `config.py` hardcodes
`SECRET_KEY = "bhoomi-secret-key-super-secure-key-2026-gov-nic"` with no env override, and
`CORS_ORIGINS` / the actual middleware use `allow_origins=["*"]` **with**
`allow_credentials=True`. There is no `.env`, no `.env.example`.

### 4.9 — P1 · Location hierarchy validator produces false positives

When the exact 4-tuple lookup misses, the fallback searches `MasterLocation` by
**village name alone** and reports a mismatch — even when the tehsil is identical. The live
DB contains the resulting nonsense:

> `Location hierarchy mismatch: Village 'Dobhi' belongs to Tehsil 'Sherghati', not 'Sherghati'.`

### 4.10 — P1 · Broken and machine-specific file paths

`document_pages` rows in the live DB:

```
docs 1–5:  /data/uploads/doc_N_pages/page_1_raw.png            (absolute, wrong root)
docs 6–7:  /Users/varunyadav/.gemini/antigravity/scratch/...   (a different person's Mac)
```

Seeded documents point at `/app/data/demo_documents/*.pdf`, which does not exist. Every
seeded document's "view original" and page-image request will 404. The verification
workspace — the flagship screen — cannot display a source document for any seeded record.

### 4.11 — P1 · Synchronous processing inside the HTTP request

`POST /processing/{id}/start` runs PDF render + OpenCV + Tesseract + N network round-trips
to Google Translate, line by line, in the request thread. A 20-page scan will exceed any
reasonable proxy timeout. There is no job table, no progress, no retry, no cancellation.
`/pipeline-status` infers stage completion from the presence of rows rather than reading
real job state. PRD §20 specifies an explicit state machine; it isn't implemented.

Related: only page 1 is ever OCR'd. `convert_to_pages` renders every page correctly, then
`processing.py` selects `page_number == 1` and discards the rest.

### 4.12 — P2 · No migrations, no version control, no data-provenance flag

- `Base.metadata.create_all()` only — no Alembic. Any model change requires deleting the DB.
- **There is no `.git` directory.** No history, no branches, no rollback before a refactor.
- No `is_demo` / `source_class` column anywhere. Seeded documents are counted in dashboard
  statistics indistinguishably from real uploads. PRD §33 and MASTER BUILD PROMPT §19 both
  require this separation.
- `bhoomi_land_records.db` (454 KB, containing bcrypt hashes) sits in the working tree.
- `frontend/dist/` (a 941 KB built bundle) is committed alongside source.

### 4.13 — P2 · PostGIS deployed but unused; GIS georeferencing invented

`docker-compose.yml` provisions `postgis/postgis:16-3.4`. No model uses a `Geometry` column,
no spatial index exists, and every "spatial" query is a plain `ilike` on text. In
`cadastral_map_service.py`, vectorised contours are mapped to coordinates by
`lng = 80.05 + (px/width)*0.015` — an arbitrary linear stretch anchored to a fixed
Bilhaur lat/lng with no control points, no CRS, and no georeferencing — then emitted as
GeoJSON that renders on a real basemap. Khasra numbers for detected polygons are invented
as `450 + index`. On failure it silently returns a synthetic 6-parcel naksha labelled
"Vectorized from Cadastral Naksha".

### 4.14 — P2 · Dead code and leftovers

- `document_service._generate_synthetic_land_record_canvas()` — the removed fake renderer, still present.
- `models/location.py`: `ForeignKey("tehsil.id" if False else "tehsils.id")` — debug artefact.
- `master_locations` duplicates the `states/districts/tehsils/villages` hierarchy.
- `Settings.jsx` — a settings form whose submit handler sets a "Saved" flag and calls nothing.
- `layout_service` adds nothing beyond passing through the fake OpenCV regions.
- `start.sh` — bash, references a non-existent `backend/venv`, on a Windows machine.
- `docker-compose.yml` retains the obsolete `version: '3.8'` key (PRD §28 says not to rely on it).

---

## 5. UX assessment

**Working:** consistent restrained government aesthetic, no emoji-as-design, sensible
sidebar IA, role-gated admin nav, bilingual (en/hi) shell, split-screen verification
workspace concept is right.

**Problems:**
1. **No parcel-centric screen exists.** Every screen is a list of documents or rows. There
   is nowhere to answer "what is the history of Khasra 127/2?"
2. **"Why does the system believe this?" is unanswerable.** Fields show a confidence pill;
   clicking cannot reach a verifiable source region (§4.6, §4.10).
3. Two purely decorative pages (`Reports`, `Settings`).
4. Login page presents six credentials to the user — reads as a toy, not a government system.
5. Sidebar advertises "13+ Indic Languages Online" with a live-status indicator that
   reflects nothing.
6. No empty/error states on most pages; no loading skeletons for the multi-minute pipeline.

---

## 6. Preserve / refactor / delete

### PRESERVE (keep and build on)
`auth/jwt.py` · `auth/rbac.py` · `api/v1/admin.py` · `api/v1/auth.py` · `api/v1/locations.py` ·
`models/location.py` · the 36-state geography seed · `services/document_service.convert_to_pages` ·
`utils/opencv_utils.preprocess_image_for_ocr` · `services/language_detection_service.py` ·
`services/translation_service.py` (identifier masking especially) · `utils/terminology.py` ·
`services/duplicate_service.py` · `services/audit_service.py` · `services/learning_service.py` ·
frontend shell (`App.jsx`, `api.js`, layouts, common components, contexts, locales) ·
`AdminManagement.jsx` · `DocumentUpload.jsx` · `DocumentsRepository.jsx` · `GISMap.jsx`

### REFACTOR (right idea, wrong implementation)
| Component | Change |
|---|---|
| `ocr_service.py` | Keep the `BaseOCREngine` abstraction. Delete the fabricating engine. Add a real failure path. Emit per-word boxes + real confidences. |
| `extraction_service.py` | Keep the regex/terminology approach. Replace invented confidence with values derived from the backing OCR regions. Never emit a bbox that OCR did not provide. |
| `validation_service.py` | Promote to a versioned rule registry emitting structured `Finding` objects. Fix the hierarchy false positive. |
| `models/*` | Extend into the parcel-centric evidence graph (spec doc). Add Alembic. |
| `processing.py` | Convert to an orchestrated job with a real state machine; process all pages. |
| `dashboard.py` | Delete every fabricated fallback. Return real counts, or explicit "no data". |
| `verification.py` | Add RBAC. Remove hardcoded value fallbacks. Write officer corrections as new superseding claims rather than mutating originals. |
| `VerificationWorkspace.jsx` | Rebuild the evidence pane around real regions, with an honest "no source region available" state. |
| `cadastral_map_service.py` | Keep contour detection; mark output `UNGEOREFERENCED`; stop inventing khasra numbers; remove the silent synthetic fallback. |
| `seed_data.py` | Split into geography seed (always) and demo corpus (flag-gated, `source_class=SEED_SYNTHETIC`). |

### DELETE
- `HybridIndicOCREngine` (entire class) — **highest priority deletion in the project**
- `document_service._generate_synthetic_land_record_canvas`
- `cadastral_map_service._generate_demo_vectorized_naksha` (or gate behind an explicit demo flag with a visible label)
- Hardcoded `confidence_distribution` / `processing_timeline` / `state_progress` fallbacks in `dashboard.py`
- Hardcoded value fallbacks in `verification.py` (`"456"`, `"142"`, `"राम प्रसाद"`)
- `DEMO_PRESETS` in `Login.jsx` and the password map in `AuthContext.switchRole` (gate behind `VITE_DEV_LOGIN=true`)
- Fabricated chart data in `Reports.jsx`
- `master_locations` (after migrating the validator onto the real hierarchy)
- `frontend/dist/` and `backend/bhoomi_land_records.db` from the tree
- **Database rows: documents 6 and 7** and all their derived fields — contaminated fabrications
- The `"tehsil.id" if False else` artefact

### MISSING (must be built)
Parcel entity · person/owner entity resolution · land events · evidence regions ·
claim supersession model · timeline reconstruction · transition analysis · event matching /
evidence-gap detection · contradiction engine · evidence sufficiency scoring · investigation
cases + prioritisation · Alembic migrations · job queue + state machine · data-provenance
classification · integration adapter interfaces (LRMS/DILRMP) · `.env` handling · rate
limiting · RBAC on domain routes · frontend tests · backend tests for real uploads ·
Parcel Intelligence / Land Time Machine / Investigation Center screens

---

## 7. Honest scorecard

| Area | Score | Note |
|---|---|---|
| Auth & user administration | 8/10 | Genuinely good; needs RBAC extended to domain routes |
| Geography master data | 9/10 | Best data asset in the repo |
| Document ingestion & rendering | 7/10 | Real PDF rendering; only page 1 is used downstream |
| Image preprocessing | 7/10 | Real CLAHE pipeline; deskew claimed but not implemented |
| **OCR** | **1/10** | **Fabricates records from arbitrary files** |
| Language detection | 8/10 | Real, deterministic, defensible |
| Translation | 7/10 | Real with correct identifier protection; fabricated confidence |
| Field extraction | 5/10 | Real regex over a good dictionary; fabricated confidence and bboxes |
| Validation | 6/10 | Real DB-backed rules; one false-positive bug; flat outputs |
| Evidence / traceability | 2/10 | Schema gestures at it; no verifiable region ever exists |
| Human-in-the-loop | 6/10 | Corrections captured well; no RBAC; overwrites AI values |
| Dashboard / reporting | 1/10 | Predominantly invented numbers |
| GIS | 3/10 | Reads real DB rows; PostGIS unused; georeferencing invented |
| Security | 3/10 | 30 open endpoints, hardcoded secret, wildcard CORS + credentials |
| Testing | 3/10 | 5 tests; the OCR test passes because OCR is faked |
| DevOps | 4/10 | Compose works in principle; no migrations, no env, no git |
| **Novelty vs SIH26018 baseline** | **2/10** | Everything present is a baseline requirement. Nothing yet is the differentiator. |

---

## 8. What this means

The repository is a **credible baseline-features prototype with a fabrication layer bolted
underneath it**. The fabrication layer is not a shortcut a judge will overlook — it is
reachable in under sixty seconds by uploading any PDF, and the proof is already sitting in
the committed database.

The build order that follows from this audit is therefore not "add the differentiator".
It is:

1. **Make the system honest** (delete fabrication, fail loudly, real confidences, RBAC).
2. **Make it parcel-centric** (evidence graph + parcel identity).
3. **Then** build the differentiator — reconstruction, contradiction, evidence gaps,
   sufficiency, prioritised investigation — on top of a foundation that cannot lie.

Step 1 is unglamorous and non-negotiable. A system that reconstructs parcel history from
fabricated OCR is worth less than nothing.

Target architecture, domain model, engine designs and the phase plan are in
**`BHUMI_FORENSICS_SPEC.md`**.
