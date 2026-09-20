# BHUMI FORENSICS

**Evidence-backed land record intelligence and parcel reconstruction.**
Smart India Hackathon 2026 · Problem Statement **SIH26018**

> We don't just extract what a land document says.
> We reconstruct whether the history of a land parcel makes sense.

**Design principle:** *AI proposes. Evidence explains. The authorised officer decides.*

---

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Repository audit + target architecture | Complete — [`ARCHITECTURE_AUDIT.md`](ARCHITECTURE_AUDIT.md), [`BHUMI_FORENSICS_SPEC.md`](BHUMI_FORENSICS_SPEC.md) |
| 1 | Honesty & safety: no fabrication, RBAC, real metrics, migrations | Implemented — [`PHASE1_CHANGES.md`](PHASE1_CHANGES.md) |
| 2 | Evidence foundation: append-only OCR runs + per-word evidence regions | Implemented — [`PHASE2_CHANGES.md`](PHASE2_CHANGES.md) |
| 3 | Parcel identity: durable parcels/persons resolved from claims | Implemented — [`PHASE3_CHANGES.md`](PHASE3_CHANGES.md) |
| 4 | Reconstruction: year-by-year parcel timeline from claims | Implemented — [`PHASE4_CHANGES.md`](PHASE4_CHANGES.md) |
| 5 | Event matching + contradiction/evidence-gap detection | Implemented, tested (63 passed) — [`PHASE5_CHANGES.md`](PHASE5_CHANGES.md) |
| 6 | Evidence sufficiency scoring + finding prioritisation | Implemented — [`PHASE6_CHANGES.md`](PHASE6_CHANGES.md) |
| 7 | Officer workflow: assign / comment / resolve, end-to-end | Implemented — [`PHASE7_CHANGES.md`](PHASE7_CHANGES.md) |
| 8 | Parcel Intelligence UI + public `/story` page | Implemented — [`PHASE8_CHANGES.md`](PHASE8_CHANGES.md) |

The core differentiator — parcel history reconstruction, contradiction detection,
evidence-gap detection, sufficiency scoring and prioritisation, and the officer
workflow that acts on it — is built and wired end to end, from document upload
through to a signed-in officer's queue and a public `/story` walkthrough for
anyone without an account.

---

## What actually works today

- Real document upload (PDF / JPEG / PNG / TIFF), magic-byte validated, SHA-256 deduplicated
- Real PDF rendering (PyMuPDF) and OpenCV preprocessing (deskew, CLAHE, denoise, adaptive threshold)
- Real OCR (Tesseract) over **every page**, with per-word bounding boxes and per-word confidences, kept as append-only OCR runs
- Script and language detection across 12 Indic scripts by Unicode block analysis
- Identifier-protected translation (survey / khasra / khata / registration numbers and dates are masked before translation and restored after)
- Regex + terminology-dictionary field extraction with state-specific aliases (UP, MP, Bihar, Maharashtra, Rajasthan, Punjab, Karnataka)
- Four-tier validation: field rules, location hierarchy, cross-registry comparison, duplicate detection
- **Parcel identity resolution** — claims about the same khasra/khata/village converge on one durable `Parcel`, with every raw identifier spelling and person-name spelling kept as an alias
- **Timeline reconstruction** (`GET /parcels/{id}/timeline`) — real year-by-year snapshots and transitions computed live from claims, no fabricated history
- **Event matching + contradiction/evidence-gap detection** — material transitions are matched against known land events; unmatched ones become `EVIDENCE_GAP` findings, incompatible independent claims become `CONTRADICTION` findings with both sources cited
- **Evidence sufficiency scoring + prioritisation** — a reproducible score per parcel and a priority-ordered investigation queue, not a black-box ranking
- **Officer workflow** — assign, comment, resolve findings and investigation cases end to end
- **Parcel Intelligence UI** (`/parcels`, `/parcels/:id`) — current state, Land Time Machine (year slider), evidence graph, conflicts, evidence gaps, and the investigation panel, all in one tabbed screen
- **Public `/story` page** — a citation-backed, six-chapter walkthrough of the problem and approach, reachable without an officer account
- Human verification workspace showing the **actual scanned page** with OCR-derived source regions
- Officer corrections stored separately from AI output, with full audit trail
- JWT auth with bcrypt, role-based access control on every endpoint but login
- Cadastral map viewer (Leaflet) and an **ungeoreferenced** map-sheet vectoriser
- 12-language UI localisation (English, Hindi, and 10 other Indic languages)

### What it deliberately does not do

- It does not claim OCR **accuracy**. It reports engine **confidence**. Accuracy needs a labelled evaluation set, which has not been run.
- It does not fabricate. If OCR cannot read a page, or the text is not a land record, processing fails with an explicit reason and stores nothing.
- It does not invent bounding boxes. A value with no OCR geometry is shown without a highlight and says so.
- It does not claim government integration. `MasterLandRegistry` is a clearly labelled mock.
- It does not georeference vectorised map sheets. Traced outlines are returned in normalised image coordinates, marked `VECTORIZED_UNGEOREFERENCED`.
- It does not claim to be an official government portal. `/story` and the login footer say plainly this is an SIH 2026 prototype.
- Agents do not decide anything. Verification and every resolution action is a human action.

---

## Architecture

```
frontend/          React 18 · Vite · Tailwind · Leaflet · Recharts · 12-language i18n
backend/
  app/api/v1/      17 routers — auth, documents, processing, records, verification,
                   validation, parcels, findings, investigation_cases, evidence,
                   analytics, dashboard, gis, learning, admin, audit, notifications, locations
  app/auth/        JWT + capability-based RBAC
  app/core/        typed error hierarchy — every stage fails loudly
  app/models/      SQLAlchemy models (provenance columns throughout)
  app/services/    ocr · extraction · translation · validation · confidence · gis
                   · identity resolution · timeline building · transition analysis
                   · event matching · contradiction detection · evidence sufficiency
                   · priority scoring · investigation · learning · notifications · audit
  alembic/         migrations — the single schema authority
  scripts/         operational tooling
  tests/           anti-fabrication, RBAC, honest-metrics, parcel identity, timeline,
                   event matcher, findings, officer workflow, sufficiency scoring suites
docker-compose.yml PostgreSQL/PostGIS + backend + nginx frontend
```

Pipeline, upload to insight:

```
upload → validate → render pages → enhance → OCR (all pages)
      → detect script → translate → extract → score confidence → validate
      → human verification → parcel identity resolution
      → timeline reconstruction → event matching → contradiction / gap detection
      → sufficiency scoring → prioritisation → officer workflow (assign/comment/resolve)
```

Every stage either produces a result derived from the uploaded file and prior
claims, or raises. Nothing downstream of upload is invented.

---

## Running it

Prerequisites: Python 3.11+, Node 20+, and **Tesseract with the language packs you need**.

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                 # SECRET_KEY auto-generates in development
alembic upgrade head
pytest -v
uvicorn app.main:app --reload --port 8000

# Frontend
cd ../frontend
cp .env.example .env.local
npm install
npm run dev
```

- UI: http://localhost:5173
- Public walkthrough (no login required): http://localhost:5173/story
- API: http://localhost:8000 · docs at `/docs` (disabled in production)
- `GET /health` reports which OCR language packs are actually installed.

### Docker

```bash
cp backend/.env.example backend/.env      # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

The backend image runs `alembic upgrade head` before serving. The frontend image is
built with `VITE_ENABLE_DEV_LOGIN=false`, so no development account list ships in it.

### Accounts

Development seeds six accounts covering the role hierarchy (super admin, state admin,
district officer, tehsil officer, verification officer, public viewer). Their passwords
live in `backend/app/database/seed_data.py` under the development branch only — they are
**not** in the frontend bundle and **not** in this README.

Outside development, set `SEED_DEFAULT_PASSWORD` or create the first administrator
manually; there are no built-in credentials.

---

## Configuration

Everything security-relevant comes from the environment — see `backend/.env.example`
and `frontend/.env.example`.
`SECRET_KEY` is required in production and the server refuses to start without it.
`CORS_ORIGINS=*` is rejected in production because the API sends credentials.

## Data policy

| Class | Meaning |
|---|---|
| `REAL_UPLOAD` | A file a user uploaded. Counted in operational metrics. |
| `SEED_SYNTHETIC` | Development/demo fixtures. Excluded from metrics by default, labelled in the UI. |
| `EXTERNAL_IMPORT` | Reserved for future integrations. |

Seed data never becomes a fallback for real processing, and **no documents are seeded** —
they only enter through upload and real processing.

---

## Documentation

- [`ARCHITECTURE_AUDIT.md`](ARCHITECTURE_AUDIT.md) — what the codebase was, with evidence
- [`BHUMI_FORENSICS_SPEC.md`](BHUMI_FORENSICS_SPEC.md) — target architecture, domain model, engines, roadmap
- [`PHASE1_CHANGES.md`](PHASE1_CHANGES.md) through [`PHASE8_CHANGES.md`](PHASE8_CHANGES.md) — what each phase changed and how to verify it
