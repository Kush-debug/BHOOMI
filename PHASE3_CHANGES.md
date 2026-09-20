# Phase 3 — Parcel Identity

**Status:** implemented, not yet run. Written after your Claude Code session
confirmed Phase 1+2 pass (48 passed, 1 deliberately-skipped) with Tesseract
installed — this phase builds directly on that verified foundation. Same
static-only verification as before on my end (`py_compile` + import checks);
`pytest -v` is what proves it actually works.

**Division of labor note:** per your Claude Code session's proposal, I'm
staying out of test/config/infra and flagging test-file changes. This phase
adds one **new** test file (`tests/test_parcel_identity.py`) — it doesn't
touch `conftest.py` or anything your session already fixed.

---

## 1. What this is, per BHUMI_FORENSICS_SPEC.md §3.2 / §9 Phase 3 gate

> Gate: **"Two documents about one Khasra converge on one parcel."**

Before this phase, every `Claim` stood alone — two documents about the same
plot of land had no relationship in the database beyond both existing. This
phase adds the durable entity documents are evidence *about*:

| Table | Purpose |
|---|---|
| `parcels` | One row per real plot of land, keyed by normalised khasra number + administrative location. Durable across every document that ever mentions it. |
| `parcel_identifier_aliases` | Every raw spelling of the khasra number that has resolved to this parcel (`"340-1"`, `"340/1"`, `"३४०/१"` all point here), and how it matched. |
| `persons` | One row per real landowner, so `"Suman Tripathi"` and `"Suman  Tripathi"` (extra whitespace) don't get read as two different people, or — worse — as an ownership change once Phase 5 looks for those. |
| `person_aliases` | Every raw name spelling that resolved to a person. |

`claims.parcel_id` and `claims.person_id` (both nullable) are the new link.
They're set by a new pipeline stage — RESOLVE, between EXTRACT and CONFIDENCE
in `/processing/{id}/start` — which never blocks processing: a document with
no khasra number simply has unresolved claims, which is the honest state.

## 2. How resolution actually works

**Parcels** (`app/services/identity_resolver.py::resolve_parcel`): the khasra
number is normalised — Unicode digit folding (Devanagari/Tamil/Telugu/Kannada
→ ASCII, via `unicodedata.digit()`, not a hand-built table, so it isn't
limited to the four languages currently wired into extraction) plus separator
canonicalisation (`"340-1"` and `"340 / 1"` both become `"340/1"`) — then
combined with state/district/tehsil/village into a `parcel_key`. Exact match
on that key wins; failing that, an alias lookup catches a previously-seen raw
spelling in the same village; failing that, a new parcel is created. Every
resolution — including a repeat one — records the raw string as an alias if
it hasn't been seen before, so `/parcels/{id}` can show every way this
parcel's khasra number has actually appeared across documents.

**Persons** (`resolve_person`): exact match on a normalised name (NFKC,
casefolded, whitespace-collapsed) is the *only* automatic merge. I want to be
upfront about a scope cut here: `BHUMI_FORENSICS_SPEC` §5.2 calls for
"script-aware normalisation + a phonetic key + edit distance." A real
phonetic algorithm doesn't have an off-the-shelf equivalent across
Devanagari/Tamil/Telugu/Kannada without a language-specific transliteration
model — that's a real ML component, not a function I can write correctly in
this pass. What's implemented is more conservative than the spec describes:
edit-distance near-matches are computed and available as
`review_candidates` on the resolver's return value, but nothing auto-merges
on them — only an exact normalised match creates a link automatically. I'd
rather ship the honest, narrower version than claim phonetic matching that
isn't real. If you want the full version, it needs either a proper
transliteration library per script or a human-reviewed merge queue; either
is a scoped follow-up, not a quick add.

## 3. API

```
GET /parcels?q=<khasra, khata, or village text>   -- search, any script/separator
GET /parcels/{id}                                 -- identifiers, aliases, linked
                                                       documents, persons, claims
```

`/parcels/{id}` is the direct proof of the gate: `document_count` on a parcel
search result, and the `documents` array on the detail response, show every
document that resolved to this parcel — upload the same khasra number twice
and you'll see `document_count: 2`, not two separate parcels.

## 4. Migration

`alembic/versions/0003_phase3_parcel_identity.py` — purely additive: four new
tables, two new nullable columns on `claims` (`parcel_id`, `person_id`).
Nothing is migrated or backfilled; existing claims just have NULL
parcel/person links until their document is next reprocessed. No downgrade
data loss risk either way — the downgrade drops the new tables/columns
cleanly since nothing else depends on them yet.

One thing worth knowing: on an existing `claims` table (the ALTER TABLE ADD
COLUMN path, not a fresh `CREATE TABLE`), the new `parcel_id`/`person_id`
columns don't get a real foreign-key constraint at the database level — same
limitation the 0001 and 0002 migrations already have for their added
columns. The ORM model declares the FK either way; it's just not enforced by
SQLite in this path. Not a new problem, just flagging it stays true here too.

## 5. Tests

`tests/test_parcel_identity.py`, new — two real PDFs per test, pushed through
upload → process, distinct content per test (SHA-256 dedup, same pattern as
Phase 2's tests):

| Test | Proves |
|---|---|
| `test_two_documents_same_khasra_converge_on_one_parcel` | two documents with the same khasra number (deliberately spelled `"340-1"` vs `"340/1"` to also prove separator normalisation) converge on one parcel with `document_count: 2`; their owner names (with a whitespace variation) resolve to one Person |
| `test_different_khasra_creates_a_distinct_parcel` | a different khasra number in the same village produces a disjoint parcel id — resolution isn't just "first parcel wins" |

## 6. What Phase 3 deliberately did not do

- No real cross-script phonetic person matching — see §2's honesty note.
- `village_id` on `Parcel` (the FK into the real location hierarchy) is
  declared but never populated by the resolver yet — it currently matches on
  the document's free-text state/district/tehsil/village strings, the same
  way `validation_service.py`'s existing hierarchy check does. Wiring actual
  village-row resolution is straightforward but deliberately deferred rather
  than touching `validation_service.py` in this pass, since that file is
  correct and already tested.
- No timeline, transitions, or contradiction detection — that's Phases 4–5,
  and they're what actually consume `parcel_id` for something a user sees on
  screen (a Land Time Machine, an unexplained-transition flag). Phase 3 on
  its own only proves convergence, which is why the gate is phrased that way.
- The frontend was not touched. There's no Parcel Intelligence screen yet
  (Phase 8) — `/parcels` is reachable at `/docs` and by the tests, not from
  the UI.

## 7. Run it

Same sequence — the new migration is picked up by `alembic upgrade head`
automatically. New commands beyond last time: none. Just:

```bash
pytest -v tests/test_parcel_identity.py
```

(or the full `pytest -v` — everything from Phase 1/2 should still be green,
this phase didn't touch any of those files' logic, only added new tables and
one new pipeline stage that runs after claims are already committed).
