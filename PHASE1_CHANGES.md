# Phase 1 — Honesty & Safety

**Status:** implemented, **not yet executed**. This container has no PyPI or npm
access, so nothing below has been run. Every file compiles (`py_compile`), all
cross-module imports resolve (static check), and the JSX is brace-balanced — but
the commands in §4 are what actually prove it.

---

## 1. The finding that drove this phase

`backend/app/services/ocr_service.py` contained `HybridIndicOCREngine`. It never
opened the image. It branched on the **upload form metadata** and returned
hand-written land-record text with hand-written bounding boxes and confidences of
0.94–0.99. `OCRService.process_image` fell through to it silently whenever
Tesseract was missing, raised, or returned under 20 characters.

Your committed database already held the result:

| id | file | status | "OCR" the system stored |
|---|---|---|---|
| 6 | `Varun_Yadav_Resume (1).pdf` | verification_pending | Hindi Khasra B-1 for Gaya / Sherghati / Dobhi |
| 7 | `Varun_Yadav_Resume (1).pdf` | **processed** | Tamil Patta: owner *Ramasamy*, survey *123/4*, area *0.85*, deed *TN-REG-2023-4512* |

None of those values exist in that file.

---

## 2. What changed

### Fabrication removed
- **Deleted `HybridIndicOCREngine`.** `OCRService` now dispatches to one engine and has
  no `except` clause at all — a test asserts that, so a fallback cannot creep back.
- OCR returns **real Tesseract word boxes, word confidences, page dimensions,
  engine version and language packs used**. Failure raises `OCR_ENGINE_UNAVAILABLE`
  or `OCR_EMPTY_RESULT` with the character count and likely causes.
- New failure `NO_LAND_RECORD_FIELDS_FOUND`: OCR worked, but nothing in the text is a
  land record. The document is marked `failed`, stores the reason, and the upload
  screen shows what the OCR actually read.
- **No invented bounding boxes.** A field gets geometry only when its value is matched
  back to Tesseract word boxes; otherwise `bounding_box` is `NULL` and
  `bbox_source = NONE`. The workspace says *"no source region available"* instead of
  highlighting an arbitrary rectangle.
- **Confidence is derived, never asserted.** It comes from the OCR words behind the
  value, and validation may only *lower* it. Unmeasurable → `NULL` → the UI renders
  "not measured". Removed literals: `0.98/0.96/0.94` in extraction, `0.96` in
  validation, `0.90` in translation, `0.94/0.95` column defaults, and the frontend's
  `|| 0.96` display fallbacks.
- **Deleted the dead synthetic-document canvas generator** and the fake
  `detect_table_grid_and_stamps` (three boxes computed as percentages of image size,
  labelled as OpenCV contour detection). Replaced with real morphological line detection.
- **Deskew implemented.** The docstring claimed it; the code never did it.
- **Cadastral vectoriser no longer invents georeferencing.** It returned
  `lng = 80.05 + (px/width)*0.015` from a fixed Bilhaur anchor, invented khasra numbers
  as `450 + index`, and silently returned a synthetic village map on failure. Now:
  normalised image coordinates, `VECTORIZED_UNGEOREFERENCED`, no invented labels,
  failure raises.
- **Translation fails loudly.** It used to return the untranslated original at
  "confidence 0.40" as though it were a translation.

### Fabricated numbers removed
- **Dashboard** computed entirely from queries. Gone: `total_documents: 25430`, the
  Mon–Sun activity timeline, the confidence histogram, the invented state totals.
  Unmeasured values return `null`, not a plausible default. Real uploads and demo data
  are counted separately (`scope`, `demo_documents_excluded`).
- **`Reports.jsx`** rewritten against two new endpoints, `/analytics/quality` and
  `/analytics/throughput`. It reports engine **confidence**, and says in the UI that
  confidence is not accuracy because no labelled evaluation has been run. Adds an
  evidence-grounding panel: how many extracted values have a real source region.
- **`Settings.jsx`** was a form whose submit handler set a "Saved" flag and called
  nothing. Now a read-only view of the server's actual OCR capability and processing policy.
- **Sidebar** claimed "13+ Indic Languages Online" with a live status dot. It now
  reports `/processing/engine-status`: engine, version, installed packs, or a red
  "Unavailable".
- **Seed data no longer creates documents.** It used to insert five complete documents
  with fake OCR, fake fields and fake confidences — including the demo's flagship
  anomaly, whose `rule_name` (`MASTER_REGISTRY_AREA_MATCH`) does not exist in
  `validation_service`. It was a literal, not an engine output. Reference data
  (geography, mock master registry, users, tagged GIS parcels) still seeds.
- **`verification.py`** no longer falls back to `"456"`, `"142"`, `"राम प्रसाद"`, `0.0`
  when approving. Missing mandatory fields return 422 naming them.

### Security
- **30 public endpoints → 0.** 49 endpoints; only `POST /auth/login` is public.
  Capability groups (`CAN_UPLOAD`, `CAN_EXPORT_REGISTRY`, `CAN_READ_AUDIT`, …) in
  `auth/rbac.py`. Viewers see only verified records. Registry CSV export is restricted
  and audited. Resolving a finding requires a reason and is audited.
- **`SECRET_KEY` from environment.** Production refuses to start without one;
  development generates a machine-local key in `backend/.dev_secret` (gitignored).
  The hardcoded `bhoomi-secret-key-super-secure-key-2026-gov-nic` is gone.
- **CORS from environment**, and `*` is rejected in production (the API sends credentials).
- **No credentials in the frontend bundle.** `DEMO_PRESETS` and the duplicate password
  map in `AuthContext.switchRole` are gone. A dev account picker fills the *username*
  only, behind `VITE_ENABLE_DEV_LOGIN`, which the Docker build sets to `false`.
- **Upload hardening:** magic-byte sniffing (not extension trust), size limit from
  config, SHA-256 duplicate detection, filename sanitisation on every path built from
  user input.
- Token lifetime 24h → 8h.

### Correctness
- **Every page is OCR'd.** `convert_to_pages` rendered all pages; the pipeline then
  processed only page 1 and discarded the rest. The workspace has a page navigator.
- **The workspace shows the actual scan.** The left pane rendered OCR text on a
  simulated paper background — the officer never saw the document, and the region
  overlay had nothing to point at. It now loads the real page image (authenticated
  blob fetch, since `<img src>` cannot carry a bearer token) and scales OCR geometry
  to the displayed size.
- **Location-hierarchy false positive fixed.** It matched on village name alone and
  emitted *"Village 'Dobhi' belongs to Tehsil 'Sherghati', not 'Sherghati'"*.
- **Officer corrections are distinguishable** — `provenance = OFFICER_CORRECTION`,
  confidence cleared, basis recorded.
- `ForeignKey("tehsil.id" if False else "tehsils.id")` debug artefact removed.

### Infrastructure
- **Alembic is the sole schema authority.** `Base.metadata.create_all()` removed from
  `main.py`. The baseline migration is safe on a fresh database *and* on your existing
  one, and backfills provenance columns.
- `.gitignore` (databases, uploads, `.env`, `.dev_secret`, `dist/`, `node_modules/`),
  `.env.example` for both backend and frontend.
- `scripts/purge_fabricated_data.py` — finds fabricated documents by evidence
  (fabricating engine recorded, original file missing, placeholder bounding boxes),
  reports by default, deletes with `--confirm`.
- `docker-compose.yml`: obsolete `version:` key removed, password from environment,
  `env_file`, dev login forced off in the image. Backend image runs
  `alembic upgrade head` before serving.
- `alembic`, `psycopg2-binary` added; unused `pypdf` removed (PyMuPDF is the renderer).

---

## 3. Test suite

`tests/test_backend.py` was deleted. Its OCR test passed **because** of the
fabrication: it processed a seeded document whose file does not exist, so Tesseract
failed, the fallback fired, and the test asserted on invented Tamil text. Its
worthwhile parts (36 states, cascading hierarchy, admin CRUD/RBAC) are preserved.

| File | Proves |
|---|---|
| `test_no_fabrication.py` | the engine class is gone; no land-record vocabulary remains in the OCR module; `OCRService` has no `except`; missing images raise; **a CV upload is rejected with an explicit error and stores no fields**; a real land document yields *its own* identifiers; no placeholder boxes; upload-form metadata carries no confidence |
| `test_rbac.py` | 17 endpoints reject anonymous callers; a viewer cannot export, audit, read documents, resolve findings, or **approve a land record**; resolving requires a reason |
| `test_honest_metrics.py` | no old hardcoded number appears anywhere in the dashboard payload; the timeline carries real dates; unmeasured confidence is `null`; demo data is segregated; `/health` reports real OCR capability; seeding creates no documents |
| `test_seed_and_reference_data.py` | reference data intact; admin CRUD works; the old secret is gone; wildcard CORS rejected in production |

The two headline tests generate a real PDF with PyMuPDF at test time and push it
through the live upload → process path. They skip if Tesseract is absent rather than
passing vacuously.

---

## 4. Run it

```bash
cd <repo>

# 0. Version control first — there is no .git in this checkout.
git init
git add -A
git commit -m "Baseline before Phase 1"
git checkout -b phase1-honesty-and-safety

# 1. Backend environment
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

copy ..\.env.example .env      # Windows   (cp on macOS/Linux)
# ENVIRONMENT=development is enough to start; SECRET_KEY auto-generates locally.

# 2. Tesseract must be installed and on PATH.
tesseract --version
tesseract --list-langs
# Windows: https://github.com/UB-Mannheim/tesseract/wiki  (tick Hindi/Tamil/Telugu/Kannada)
# The API now starts and logs a warning if it is missing, and processing returns an
# explicit error rather than fabricating output.

# 3. Migrations
alembic upgrade head

# 4. Clean the contaminated rows (report first)
python scripts/purge_fabricated_data.py
python scripts/purge_fabricated_data.py --confirm

# 5. Tests
pytest -v

# 6. Run
uvicorn app.main:app --reload --port 8000

# 7. Frontend
cd ../frontend
copy .env.example .env.local   # sets VITE_ENABLE_DEV_LOGIN=true for local dev
npm install
npm run build                  # catches any JSX error immediately
npm run dev
```

**Please send me:** the output of `pytest -v`, of `npm run build`, and of
`tesseract --list-langs`. The first two are where I expect problems, since I could
not execute either here.

### The demo to run yourself
Upload any non-land-record PDF (a CV, an invoice) and process it. Expected: a red
panel naming the failure code, what the OCR actually read, and what to check — and
zero extracted fields. Before Phase 1 that same upload produced a named landowner.

---

## 5. What Phase 1 deliberately did not do

- No parcel entity, no evidence graph, no timeline, no contradiction or evidence-gap
  detection — those are Phases 2–5 in `BHUMI_FORENSICS_SPEC.md`.
- Processing is still synchronous. A large multi-page scan can still exceed a proxy
  timeout. Now that all pages are OCR'd this matters more, but the job queue is a
  later phase; single- and few-page documents are unaffected.
- PostGIS is still provisioned and unused.
- The demo corpus (Khasra 127/2) is not built yet — deliberately, since seeded
  documents were the problem. It arrives as real PDF files going through the real
  pipeline.
- Dashboards will look empty until you process documents. That is the honest state.
