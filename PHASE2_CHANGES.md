# Phase 2 — Evidence Foundation

**Status:** implemented, **not yet executed**. Same caveat as Phase 1: this
container has no PyPI/npm access, so nothing below has been run. Every changed
file compiles (`py_compile`) and every cross-module import was checked
statically — `pytest -v` is what actually proves it, and I still don't have
your Phase 1 results to know whether the codebase even starts cleanly yet.

If Phase 1 hasn't been run at all, run it first — `alembic upgrade head` for a
never-migrated database will pick up Phase 2's schema directly (see §3 below),
so you do not need to run the two phases as separate migration steps, but you
do need Phase 1's dependency and environment setup done first.

---

## 1. What Phase 2 is, per BHUMI_FORENSICS_SPEC.md §3.1

Before this phase, "what does the system believe and why" was one mutable row
per field (`ExtractedField`), overwritten in place on reprocess, holding only
the winning bounding box out of everything OCR actually read. That's enough to
show a value on screen. It is not enough to reconstruct a parcel's history
later (Phase 4), because history requires knowing *every* claim ever made
about a field, not just the current one.

Three new tables, all append-only:

| Table | Replaces | What's new |
|---|---|---|
| `ocr_runs` | `ocr_results` | Reprocessing adds a run and retires the old one (`is_current=False`) instead of deleting it. |
| `evidence_regions` | (nothing existed) | **Every** OCR word Tesseract found becomes its own row — not just the words that happened to match an extracted value. |
| `claims` | `extracted_fields` | A correction never edits a claim in place. It creates a new claim with `supersedes_claim_id` pointing at the old one, and flips the old one to `lifecycle_status=SUPERSEDED`. Both stay queryable forever. |

## 2. A deliberate deviation from the spec's migration table, and why

`BHUMI_FORENSICS_SPEC.md §3.4` describes this as a rename: `ocr_results` →
`ocr_runs`, `extracted_fields` → `claims`. I did that at the table/class level,
but I did **not** rename the columns or the API response shape that the
frontend and the Phase 1 test suite already depend on
(`standardized_field`, `field_value`, `bounding_box`, `bbox_source`,
`provenance`, `status`, and the `extracted_fields` / `ocr_results` keys in the
document JSON).

Reason: I have no way to execute either the backend or the frontend in this
environment. A full rename touching the API contract would mean editing
`VerificationWorkspace.jsx`, `ValidationCenter.jsx` and every consumer blind,
with no test run to catch a mistake before it reaches you. Keeping the
external shape identical means the *only* thing that changed is real
persistence behaviour underneath — the risk surface for an unverified change
is much smaller. `Document.ocr_results` and `Document.extracted_fields` are
now plain Python properties that filter the new append-only tables down to
"current state only" (`is_current` / `lifecycle_status=ACCEPTED`), so every
existing endpoint keeps returning exactly the shape it always did.

The new capability is additive: three read endpoints expose the full evidence
graph for anything that wants it (a future Parcel Intelligence screen, or you,
via `/docs`).

```
GET /documents/{id}/claims?include_superseded=true   -- current claims, or full history
GET /documents/{id}/regions                          -- every OCR word region persisted
GET /claims/{id}/evidence                             -- one claim's full provenance chain
```

If you'd rather I do the full rename (breaking the API shape, updating the
frontend to match, all in one unverified pass) instead of this compatibility
layer, say so and I'll do Phase 2b as that cleanup once Phase 1 is confirmed
running — but I'd recommend against it before you have a working baseline to
diff against.

## 3. Migration

`alembic/versions/0002_phase2_evidence_foundation.py`, safe on two starting
points, same pattern as 0001:

- **You haven't run `alembic upgrade head` yet at all.** `app.models` now
  registers `OcrRun`/`EvidenceRegion`/`Claim` instead of the old classes, so
  0001's own `create_all()` creates `ocr_runs`/`evidence_regions`/`claims`
  directly. `ocr_results`/`extracted_fields` are never created. 0002 then has
  nothing to migrate and nothing to drop — it's a no-op. **This is your
  situation**, as far as I know from this session.
- **You already ran the old 0001 and have real rows in `ocr_results` /
  `extracted_fields`.** 0002 creates the three new tables, copies every row
  forward (marking the most recent OCR run per page as current, and every
  migrated claim as `ACCEPTED`), then drops the two old tables. Nothing is
  destroyed — every row is copied, not discarded (`BHUMI_FORENSICS_SPEC` §2
  rule 4).

`0002` is deliberately **not downgradable** — collapsing append-only history
back into single mutable rows is lossy. If a rollback is ever needed, restore
from a backup taken before the migration.

## 4. Claim supersession, concretely

`app/api/v1/processing.py` (`/processing/{id}/start`): on every run, current
`ACCEPTED` claims for the document are looked up first. Fields an officer has
already corrected (`asserted_by=OFFICER`) are **never** touched by
re-extraction — the new pipeline output for that field is discarded, not
written. Every other field's old claim flips to `SUPERSEDED` and a new one is
inserted with `supersedes_claim_id` pointing back.

`app/api/v1/verification.py` (`/verification/{doc_id}/submit`): an officer's
correction now does the same thing from the other direction — old claim
frozen as `SUPERSEDED`, new claim written with `asserted_by=OFFICER`,
`provenance=OFFICER_CORRECTION`, `confidence=None`. This was previously an
in-place mutation of the one `ExtractedField` row; there was no way to see
what the AI had originally said once an officer edited it. Now there is.

## 5. Evidence regions, concretely

`app/api/v1/processing.py`: every Tesseract word box from every page —
headings, labels, punctuation, not just the handful of words that matched an
extracted field — is now written as its own `EvidenceRegion` row linked to the
`OcrRun` that produced it. A claim links to the *specific* region it was
grounded in via `evidence_region_id` (matched by page/line/word position from
`extraction_service._ground_in_ocr`, which now returns the matched OCR blocks,
not just their bounding box).

This is what makes `/claims/{id}/evidence` a real answer to "why does the
system believe this?" instead of a promise: it walks
`Claim → EvidenceRegion → OcrRun → Document` and returns all four, or an
explicit `no_evidence_reason` (`"this value could not be matched to specific
OCR words on the page"`, `"supplied on the upload form, not extracted from
the document"`, or `"an officer entered this value directly"`) when there's
nothing to walk to.

## 6. Tests

`tests/test_evidence_foundation.py`, new. Like Phase 1's tests, these upload a
real PDF (rendered with PyMuPDF at test time, distinct content per test since
upload dedups by SHA-256) and push it through the live pipeline — they don't
assert against seeded data.

| Test | Proves |
|---|---|
| `test_every_ocr_word_becomes_a_region` | region count exceeds claim count; every region carries a real bbox and `OCR_WORD_BOX` geometry source |
| `test_claim_evidence_endpoint_walks_back_to_a_real_region` | `/claims/{id}/evidence` returns a real region, OCR run and document for a grounded claim |
| `test_reprocessing_supersedes_instead_of_deleting` | a second `/process` call adds a new claim rather than overwriting; the old one is `SUPERSEDED`, not gone; the current-claims view shows exactly one row per field |
| `test_officer_correction_supersedes_and_survives_reprocessing` | an officer edit creates an `OFFICER`-asserted claim that supersedes the AI one, and a later reprocess does not silently overwrite it |

Also fixed in this pass: `scripts/purge_fabricated_data.py` still imported the
deleted `ExtractedField`/`OCRResult` classes — it would have crashed on import
the moment you ran it. Caught by the same static sweep that found everything
else; now uses `Claim`/`OcrRun`.

## 7. What Phase 2 deliberately did not do

- No `Parcel`, `Person`, or identity resolution — claims are not yet linked to
  a durable parcel entity. That's Phase 3.
- No timeline, transitions, contradiction or evidence-gap detection — Phases
  4–5.
- The frontend was not changed. It doesn't need to be for Phase 2's own gate
  (a field resolves to a real region, or honestly has none — already true),
  but it also doesn't yet expose the new evidence-graph endpoints. That's
  reasonable to add alongside Phase 8 (Parcel Intelligence UI) rather than
  bolting a "why" button onto the current workspace now.
- `extractor_version` on migrated claims is a fixed literal
  (`"phase1-migrated"`) rather than the real extractor that produced them,
  since the old schema didn't record one. New claims get the real version.

## 8. Run it

Same sequence as `PHASE1_CHANGES.md` §4 — the new migration is picked up
automatically by `alembic upgrade head` (no separate step). Please send me
`pytest -v` output for both `tests/test_no_fabrication.py` and the new
`tests/test_evidence_foundation.py` — I have real reason to want to see the
second one particularly, since the evidence-region linking logic
(`_find_region` in `processing.py`, matching by page/line/word position) is
the one piece of this phase I'm least certain survives contact with real
Tesseract output.
