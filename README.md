# BHUMI FORENSICS

## Deploy the frontend demo to Vercel

The repository includes a browser-only demo build that needs no backend. Push the project to GitHub, import it in Vercel, and set **Root Directory** to `frontend`. Use `npm run build` and output directory `dist`; no environment variables are needed. The Vercel SPA rewrite is already configured in `frontend/vercel.json`. See [`frontend/README.md`](frontend/README.md) for the jury walkthrough and demo limitations.

The Vercel build simulates OCR and keeps demo changes in browser storage. It is intended for presentation and is not the secure, authoritative production deployment described in the backend documentation below.

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
| 2–12 | Evidence graph, parcel identity, reconstruction, detection, investigation workflow | Planned — see the spec |

The differentiator — parcel history reconstruction, contradiction detection and
evidence-gap detection — is **not built yet**. What exists today is a document
digitisation pipeline that has been made honest enough to build on.

---

## What actually works today

- Real document upload (PDF / JPEG / PNG / TIFF), magic-byte validated, SHA-256 deduplicated
- Real PDF rendering (PyMuPDF) and OpenCV preprocessing (deskew, CLAHE, denoise, adaptive threshold)
- Real OCR (Tesseract) over **every page**, with per-word bounding boxes and per-word confidences
- Script and language detection across 12 Indic scripts by Unicode block analysis
- Identifier-protected translation (survey / khasra / khata / registration numbers and dates are masked before translation and restored after)
- Regex + terminology-dictionary field extraction with state-specific aliases (UP, MP, Bihar, Maharashtra, Rajasthan, Punjab, Karnataka)
- Four-tier validation: field rules, location hierarchy, cross-registry comparison, duplicate detection
- Human verification workspace showing the **actual scanned page** with OCR-derived source regions
- Officer corrections stored separately from AI output, with full audit trail
- JWT auth with bcrypt, role-based access control on every endpoint but login
- Cadastral map viewer (Leaflet) and an **ungeoreferenced** map-sheet vectoriser

### What it deliberately does not do

- It does not claim OCR **accuracy**. It reports engine **confidence**. Accuracy needs a labelled evaluation set, which has not been run.
- It does not fabricate. If OCR cannot read a page, or the text is not a land record, processing fails with an explicit reason and stores nothing.
- It does not invent bounding boxes. A value with no OCR geometry is shown without a highlight and says so.
- It does not claim government integration. `MasterLandRegistry` is a clearly labelled mock.
- It does not georeference vectorised map sheets. Traced outlines are returned in normalised image coordinates, marked `VECTORIZED_UNGEOREFERENCED`.
- Agents do not decide anything. Verification is a human action.

---

## Architecture

```
frontend/          React 18 · Vite · Tailwind · Leaflet · Recharts
backend/
  app/api/v1/      13 routers, 49 endpoints (48 authenticated)
  app/auth/        JWT + capability-based RBAC
  app/core/        typed error hierarchy — every stage fails loudly
  app/models/      SQLAlchemy models (provenance columns throughout)
  app/services/    ocr · extraction · translation · validation · confidence · gis · audit
  alembic/         migrations — the single schema authority
  scripts/         operational tooling
  tests/           anti-fabrication, RBAC, honest-metrics suites
docker-compose.yml PostgreSQL/PostGIS + backend + nginx frontend
```

Pipeline:

```
upload → validate → render pages → enhance → OCR (all pages)
      → detect script → translate → extract → score confidence → validate → human verification
```

Every stage either produces a result derived from the uploaded file, or raises.

---

## Running it

Prerequisites: Python 3.11+, Node 20+, and **Tesseract with the language packs you need**.

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example .env                              # SECRET_KEY auto-generates in development
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
- API: http://localhost:8000 · docs at `/docs` (disabled in production)
- `GET /health` reports which OCR language packs are actually installed.

### Docker

```bash
cp .env.example backend/.env      # set SECRET_KEY and POSTGRES_PASSWORD
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

Everything security-relevant comes from the environment — see `.env.example`.
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
- [`PHASE1_CHANGES.md`](PHASE1_CHANGES.md) — what Phase 1 changed and how to verify it
