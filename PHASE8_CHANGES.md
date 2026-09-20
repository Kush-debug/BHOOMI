# Phase 8 — Parcel Intelligence UI

**Status:** implemented, not yet run in a real browser. This is the first
frontend phase, and the verification story is different from every backend
phase before it - see §6.

---

## 1. What this is, per BHUMI_FORENSICS_SPEC.md §7 / §9 Phase 8 gate

> Gate: **"A judge understands the product in 60 seconds."**

Every backend phase since Phase 3 has said some version of "no frontend yet
— reachable at `/docs` and by the tests." Phase 8 is what finally puts
Phases 3–7's real engines (parcel identity, timeline reconstruction, event
matching, contradiction/gap detection, sufficiency scoring, prioritisation,
officer workflow) in front of a person instead of a Swagger page.

Three new pages, five new components, wired into the existing router and
sidebar:

```
/parcels              ParcelSearch       - find a parcel by khasra/khata/village
/parcels/:id           ParcelIntelligence - the flagship screen, tabbed:
                        ├── Current State    latest snapshot + documents/persons/aliases
                        ├── Land Time Machine year slider + transitions (explained/unexplained)
                        ├── Evidence Graph    every current claim -> "trace evidence"
                        ├── Conflicts         CONTRADICTION findings, resolve action
                        ├── Evidence Gaps     EVIDENCE_GAP findings, resolve action
                        └── Investigation     this parcel's case: assign/comment/resolve
/investigations         InvestigationCenter - cross-parcel prioritised queue (read + navigate)
```

Nothing on these pages is seeded or computed client-side. Every number,
badge, and timeline entry is exactly what its backing endpoint
(`GET /parcels/{id}`, `/timeline`, `/findings`, `/sufficiency`,
`GET /investigation-cases`, `GET /claims/{id}/evidence`) returns - a demo
corpus parcel and a parcel from a document uploaded five minutes ago render
through the identical code path, same as the backend's own honesty
discipline requires.

## 2. New files

| File | Purpose |
|---|---|
| `frontend/src/pages/ParcelSearch.jsx` | Entry point - `GET /parcels?q=` search, results link into the detail page |
| `frontend/src/pages/ParcelIntelligence.jsx` | The flagship page - fetches parcel/timeline/findings/sufficiency/cases in parallel, tab orchestration |
| `frontend/src/pages/InvestigationCenter.jsx` | Cross-parcel prioritised queue - `GET /investigation-cases`, filters by status/band |
| `frontend/src/components/parcel/LandTimeMachine.jsx` | The year-slider timeline, transitions with explained/unexplained badges, Ownership/Area history |
| `frontend/src/components/parcel/EvidenceDrawer.jsx` | The evidence graph drill-down: claim -> region -> page image -> document, plus inline correction |
| `frontend/src/components/parcel/FindingsList.jsx` | Shared renderer for Conflicts and Evidence Gaps tabs, with the Phase 7 resolve action |
| `frontend/src/components/parcel/InvestigationPanel.jsx` | This parcel's investigation case(s): priority breakdown, comments, assign/comment/resolve |
| `frontend/src/components/parcel/SufficiencyGauge.jsx` | The Phase 6 sufficiency score, expandable into its six-component breakdown |

## 3. Modified files (additive only)

- **`frontend/src/components/common/Badge.jsx`** — added `SeverityBadge`,
  `FindingStatusBadge`, `CaseStatusBadge`. No existing export touched.
- **`frontend/src/App.jsx`** — three new routes (`/parcels`, `/parcels/:id`,
  `/investigations`), each wrapped in `ProtectedRoute` with a new
  `STAFF_ROLES` constant mirroring `backend/app/auth/rbac.py`'s list
  (everyone except `viewer`) - the endpoints these pages call are all
  `CAN_READ_DOCUMENTS`/`CAN_READ_FINDINGS` (STAFF_ROLES) server-side, so a
  viewer would only hit 403s if the route were open to them.
- **`frontend/src/components/common/Sidebar.jsx`** — two new nav items
  ("Parcel Intelligence", "Investigation Center"), shown only when
  `user.role !== 'viewer'`, same reasoning as the route guard above.

## 4. How the Evidence Graph actually shows evidence

`EvidenceDrawer.jsx` calls `GET /claims/{id}/evidence` (Phase 2) and, when
`evidence_available` is true, fetches the real page image
(`GET /documents/{id}/pages/{n}`, the same authenticated-blob technique
`VerificationWorkspace.jsx` already uses for the same reason: the endpoint
needs a bearer token a plain `<img src>` can't send) and draws the region's
real bounding box as an overlay, scaled by `renderedWidth / bbox_page_width`
- not a guessed rectangle, the actual OCR word box Phase 2 persisted. When
`evidence_available` is false, it shows the real reason (`no_evidence_reason`
from the endpoint) instead of a blank claim.

One honesty note worth flagging: `VerificationWorkspace.jsx` (Phase 1/2)
already computes an equivalent `bbox`/`scale` pair but never actually
renders an overlay with it - those variables are dead code (confirmed by
the TypeScript check in §6, which flags them as unused). Phase 8 doesn't
touch that file - it builds a correct, working version of the same pattern
fresh in `EvidenceDrawer.jsx`. Wiring `VerificationWorkspace.jsx`'s own
overlay is a pre-existing gap from the architecture audit
(`ARCHITECTURE_AUDIT.md`: "Rebuild the evidence pane around real regions"),
not something Phase 8 introduced or fixed.

## 5. Design decisions made without asking, and why

- **Ownership History / Area History are not separate screens.** The spec's
  screen tree lists them as their own sub-items under Parcel Intelligence.
  They are exactly the `ownership_delta`/`area_delta` fields every
  `Transition` already carries (Phase 4/5) - filtered lists under the Land
  Time Machine tab, not two more full screens duplicating the same
  underlying data. Building them as separate screens would be duplication,
  not new information.
- **Investigation Center is a read + navigate queue; all writes happen on
  the parcel page.** `InvestigationPanel.jsx` (assign/comment/resolve) lives
  in `ParcelIntelligence.jsx`, not in `InvestigationCenter.jsx`, so there's
  one place with write actions for a case, not two that could drift.
- **"Assign to me" instead of a reassignment picker.** Reassigning a case to
  someone *other* than yourself needs a staff directory, and
  `GET /admin/users` is `super_admin`/`admin`-only (`admin.py`) - narrower
  than `CAN_MANAGE_INVESTIGATIONS` (all of `STAFF_ROLES`), which can assign
  cases. Rather than exposing the admin user list more broadly or building a
  picker most roles couldn't use, the panel offers self-assignment - the
  action the Phase 7 test itself already exercises (`_user_id` + self-assign
  in `test_investigation_case_assign_comment_resolve_and_rbac`). A full
  reassignment picker for admins is a reasonable follow-up, not built here.
- **`InvestigationCenter.jsx` resolves each case's parcel identity with its
  own `GET /parcels/{id}` call.** `GET /investigation-cases`'s list response
  carries `parcel_id` but not the parcel's khasra/village
  (`_case_dict` only attaches `parcel` when called with one, which the list
  endpoint doesn't do) - see that file's own docstring. At hackathon/pilot
  queue sizes this is a handful of parallel requests; if the queue grows
  into the hundreds, the real fix is a batch parcel-lookup endpoint, not
  more client-side fan-out. Flagging the scaling tradeoff rather than
  quietly shipping N+1 requests unremarked.
- **Claim correction lives inside the Evidence Graph drawer, not a
  standalone form.** `POST /verification/{doc}/claims/{claim}/correct`
  (Phase 7) is exposed exactly where an officer would notice a bad value -
  while looking at its evidence - rather than requiring a trip to the
  separate verification queue for a one-field fix.

## 6. Verification - different from every phase before this one

Phases 3–7's Python backend code could be checked with `py_compile` plus a
hand-rolled AST unused-import scan, because Python ships in this container.
Node ships too, but **npm has no registry access here** (confirmed again
this phase: `npx esbuild` → `403 Forbidden`), so nothing new could be
installed - no `vite build`, no ESLint, no Babel.

What actually verified this phase: this container has TypeScript
**globally pre-installed** (`tsc`, v6.0.3), and `tsc --allowJs --checkJs`
parses `.jsx` files as real JavaScript+JSX - full syntax parsing (mismatched
tags, unbalanced braces, illegal syntax all produce hard errors) plus
unused-variable analysis across the whole reachable import graph, even
though import *resolution* fails for every package (no `node_modules`),
which is an expected, filtered-out class of error
(`TS2307 Cannot find module`), not a real one. Confirmed the checker isn't
just silently passing everything: a deliberately broken test file
(unclosed `<span>`) was correctly rejected with `TS17008: JSX element
'span' has no corresponding closing tag` before checking the real files.

Run against all 8 new files and the 3 edited files, with
`--noUnusedLocals --noUnusedParameters`:

- **Zero syntax errors** in every Phase 8 file.
- **Zero unused-import/unused-variable warnings** in every Phase 8 file.
- The same run, run across the *whole* existing frontend (every file Phase
  8 imports, transitively), independently reproduced the exact
  `VerificationWorkspace.jsx` dead-code finding described in §4
  (`useRef`, `viewMode`/`setViewMode`, `activeFieldHasRegion`, `scale`, and
  five unused icon imports, all pre-existing) plus several more pre-existing
  unused-import findings in other untouched files (`Dashboard.jsx`,
  `Header.jsx`, `AdminManagement.jsx`, `Login.jsx`, and others) - none of
  which Phase 8 touches or is responsible for, but reported here since the
  same sweep that verified this phase's own files surfaced them.

This is stronger verification than any prior phase got, but it is still not
a real build. It does not catch: a Tailwind class typo, a prop name
mismatch between a component and its parent (both sides are untyped
`.jsx`, so `tsc` can't see the mismatch), a lucide-react icon name that
doesn't exist in the pinned version (icon imports were cross-checked by
name only, not against the actual package - `frontend/package.json` pins
`"lucide-react": "^1.16.0"`, not installed here), or any runtime behaviour
at all. `npm run dev` / `npm run build` is what actually proves this phase
works, and it's the first thing to run.

## 7. What Phase 8 deliberately did not do

- **No GIS screen integration.** The spec lists GIS as its own top-level
  screen (Phase 10). Parcel Intelligence doesn't embed a map.
- **No Analytics/Command Center wiring.** Also later phases (11).
- **No reassignment picker for cases** - see §5's "assign to me" note.
- **No case/finding reopening UI** - Phase 7's backend doesn't expose it
  either (see `PHASE7_CHANGES.md` §6), so there's nothing to wire up yet.
- **`VerificationWorkspace.jsx` is untouched** - its own dead bbox-overlay
  code (§4) is a pre-existing gap from the architecture audit, not
  something this phase's job to fix while building a new, separate
  evidence-drill-down surface.
- **No i18n catalog entries.** New UI text is plain English strings, not
  `t('key', 'fallback')` calls into `locales/en.json`/`hi.json` - Phase 8
  is UI structure and data wiring; translating five new screens is a
  separate, mechanical pass better done once the copy is stable.

## 8. Run it

No backend changes, no new migration. Frontend only:

```bash
cd frontend
npm run dev
# sign in as any non-viewer role, then:
#   Sidebar -> Parcel Intelligence -> search a khasra number that has
#   documents processed against it (e.g. one from the Phase 7 test corpus,
#   or your own demo upload) -> open it -> walk all six tabs
#   Sidebar -> Investigation Center -> confirm the queue lists real cases
```

The most useful first check is exactly what the gate asks for: open a real
parcel's Land Time Machine and see whether a judge who has never seen this
project could understand what happened to it in under a minute.
