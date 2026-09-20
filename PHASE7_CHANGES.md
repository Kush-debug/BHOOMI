# Phase 7 — Officer Workflow

**Status:** implemented, not yet run. Static-only verification on my end
(`py_compile` across the whole `backend/app`/`alembic` trees + import
checks); `pytest -v tests/test_phase7_officer_workflow.py` is what actually
proves it.

**This phase touches `verification.py` for the first time.** Every other
phase either wrote new files or edited files I had already written myself
(Phase 3/4/6) or files your Claude Code session verified and I left alone
(Phase 5's detection engines). `verification.py` is different: it's Phase
1/2 code, already carrying real behaviour (the approve/reject/correct flow),
and I have no test run to catch a mistake in it. I've flagged exactly what
changed and why in §3 below rather than asking you to trust it.

---

## 1. What this is, per BHUMI_FORENSICS_SPEC.md §5.9/§6, §9 Phase 7 gate

> Gate: **"End-to-end golden flow runs."**

Phase 6 built the prioritised queue and deliberately left it inert —
`InvestigationCase.assigned_to`/`comments`/`resolution` were declared but
nothing wrote to them, and `Finding.resolution_status` had no endpoint to
move it off `OPEN` since Phase 5. Phase 7 is what actually lets an officer
work a case end to end:

```
POST /findings/{id}/resolve                          -- move a finding off OPEN
POST /investigation-cases/{id}/assign                 -- pick up a case
POST /investigation-cases/{id}/comment                -- log progress
POST /investigation-cases/{id}/resolve                -- close a case
POST /verification/{doc_id}/claims/{claim_id}/correct  -- evidence-linked, per-field correction
```

The last one matches the spec's own §6 API surface line for line:
`POST /verification/{doc_id}/claims/{claim_id}/correct`.

## 2. New write endpoints

**`POST /findings/{id}/resolve`** (`app/api/v1/findings.py`) — body
`{resolution_status: IN_REVIEW|RESOLVED|DISMISSED, resolution_note?}`.
`RESOLVED`/`DISMISSED` require a non-empty `resolution_note` (422 without
one) — a bare status flip with no reasoning isn't an audit trail, it's a
checkbox. Already-terminal findings (`RESOLVED`/`DISMISSED`) reject a second
call with 409 rather than silently reopening. Role: `CAN_RESOLVE_FINDINGS` —
this constant already existed in `rbac.py`, unused, since whichever earlier
phase wrote the RBAC groups anticipated this endpoint before it was built.

**`POST /investigation-cases/{id}/assign`** — body `{assigned_to: user_id}`.
Validates the assignee is an active `STAFF_ROLES` user (rejects assigning a
case to a viewer, or a nonexistent id, with 422/404). Assigning an `OPEN`
case moves it to `IN_PROGRESS` — picking up a case is what starts the
investigation. Refuses on an already-`CLOSED` case (409).

**`POST /investigation-cases/{id}/comment`** — body `{text}`. Appends
`{author_id, author_name, text, created_at}` to `comments`; comments are
additive only, never edited or removed here, matching the spec's "full
audit" deliverable.

**`POST /investigation-cases/{id}/resolve`** — body `{resolution}`. Sets
`status=CLOSED`. **Deliberately independent of its findings' own
`resolution_status`** — this was flagged explicitly in `investigation_
service.py`'s Phase 6 docstring ("that closure is the officer's call, once
Phase 7 gives them a way to make it") and I kept that separation rather than
having case-resolve silently cascade into resolving every linked finding.
If findings are still `OPEN`/`IN_REVIEW` when the case closes, the response
carries a `warning` field saying so (not an error — closing a case with
open findings can be legitimate, e.g. escalated elsewhere) rather than
either blocking the close or hiding the fact.

**`POST /verification/{doc_id}/claims/{claim_id}/correct`** — body
`{new_value, notes?}`. Pairs with Phase 2's `GET /claims/{id}/evidence`: an
officer looks at the highlighted OCR region behind one claim and fixes just
that field, without submitting the whole document through `/submit`. Same
superseding-claim mechanics as `/submit` always used — see §3. A value
identical to the current one returns `{"status": "unchanged"}` rather than
creating a no-op claim; correcting an already-superseded claim id returns
404 (corrections apply to the current claim only).

Every one of these five endpoints calls `audit_service.log_event(...)` —
"full audit" per spec §3.3/§14 means every officer action that changes state
is in `audit_logs`, not just the ones that happened to already have logging.

## 3. What actually changed in `verification.py`, precisely

`submit_verification`'s per-field correction logic (the loop that supersedes
a claim when `corrected_fields` contains a changed value) is **identical
code**, moved into a new module-level function, `_supersede_claim`, and
called from both the existing `/submit` loop and the new standalone
`/claims/{claim_id}/correct` endpoint. I did not rewrite the logic — I
extracted it verbatim (field-name-for-field-name) so the two entry points
share one implementation instead of drifting into two slightly-different
copies of "how does a correction work" over time. `submit_verification`'s
observable behaviour is unchanged: same fields read, same `Claim` written,
same `learning_service.record_correction` call, same `corrections_logged`
counter.

I traced through this by hand rather than running it — flagging that
plainly, the same way I flagged the `TimelineBuilder`/`EvidenceSufficiency
Scorer` circular-import fix in Phase 6. If you or your Claude Code session
run the full suite and something in `/submit` breaks, this extraction is the
first place to look; the diff against the previous version is small and
mechanical (a block moved into a function, called by name), which should
make it fast to check.

**Separately, and not something I fixed:** `verification.py` has six
imports (`Dict`, `List`, `date`, `status`, `notification_service`,
`LandRecordResponse`) that were already unused before I touched this file —
confirmed by checking the version I pulled from your machine at the start
of this phase. I left them alone rather than cleaning up code I didn't
write and don't have a test run to verify against; noting it here so it
reads as an observation, not something Phase 7 introduced.

## 4. RBAC

One new capability group, `CAN_MANAGE_INVESTIGATIONS = STAFF_ROLES`
(`rbac.py`), covering assign/comment/resolve on `InvestigationCase`. Finding
resolution reuses the pre-existing (previously unused) `CAN_RESOLVE_
FINDINGS`. Claim correction reuses `CAN_APPROVE_RECORD`, the same role gate
`/submit` already used, since both are "can change the authoritative
record" actions.

## 5. Tests

`tests/test_phase7_officer_workflow.py`, new — three independent corpora
(separate khasra numbers, so the tests don't interact), pushed through
upload -> process -> the new endpoints:

| Test | Proves |
|---|---|
| `test_correct_claim_creates_a_superseding_claim_not_an_edit_in_place` | the per-claim endpoint writes a new `ACCEPTED` claim and freezes the old one as `SUPERSEDED` with its original value intact; identical-value correction is a documented no-op; correcting a stale claim id is rejected |
| `test_resolving_a_finding_requires_a_reason_and_survives_reprocessing` | `RESOLVED` without a note is 422; an already-resolved finding refuses a second resolve (409); **reprocessing the same parcel's document after resolving does not reset the finding to OPEN** — the one test in this project so far that proves `is_officer_owned` protection end-to-end through a real write endpoint, not just by reading `analysis_service`'s own logic |
| `test_investigation_case_assign_comment_resolve_and_rbac` | a viewer gets 403 on all three write actions and cannot be assigned a case (422); assigning an OPEN case moves it to IN_PROGRESS; a comment round-trips with the correct author; resolving closes the case and the resolution text stays free of forbidden words; a closed case refuses a second resolve |

## 6. What Phase 7 deliberately did not do

- **No case reopening.** `POST /investigation-cases/{id}/resolve` only
  closes; there's no `/reopen`. If you need that, it's a small addition —
  flagging its absence rather than building a reopen path nobody asked for
  and that could undermine the "officer decision is final until explicitly
  reversed" audit story without a clear policy on who's allowed to reverse it.
- **No finding reopening either**, same reasoning — `resolve_finding`
  explicitly refuses a second call once a finding is `RESOLVED`/`DISMISSED`.
- **Case resolve does not cascade to its findings** — see §2's `/resolve`
  entry. If you want "closing a case auto-resolves its open findings with
  the case's resolution text", that's a real, opinionated policy choice I
  didn't want to make silently.
- **No frontend** — the Investigation Center UI (spec §7's screen list) is
  Phase 8. These are read/write API endpoints, reachable at `/docs` and by
  the tests.
- **`submit_verification`'s bulk-submit path is unchanged in behaviour, but
  is the first Phase-1/2-authored file I've edited** — see §3's honesty note.

## 7. Run it

No new migration — Phase 7 added no tables, only endpoints on existing ones.

```bash
pytest -v tests/test_phase7_officer_workflow.py
# then, since this phase touched verification.py, it's worth re-running:
pytest -v
```

## 8. Follow-up fix (same day, after your Claude Code session's verification pass)

Your local session ran the full suite against the delivery above — 3/3 new
tests, 69 passed / 1 skipped overall, no regressions, `_supersede_claim`
confirmed to preserve `/submit`'s exact prior behaviour. It also caught a
real gap that predates Phase 7 (first noted during Phase 4 planning, never
circled back to): `_supersede_claim`'s `new_claim = Claim(...)` never copied
`parcel_id`/`person_id` from the claim it superseded. Both are set by
Phase 3's `IdentityResolver` and are what the Phase 4 timeline, Phase 5
findings, and Phase 6 sufficiency scoring all filter on (`GET
/parcels/{id}` and friends query `Claim.parcel_id == parcel.id`). Net
effect: a claim corrected through `/submit` or the new `/correct` endpoint
was briefly invisible to every parcel-scoped view — not wrong, just
unlinked — until the document was next reprocessed and `IdentityResolver`
re-ran.

Fix: two lines added to `_supersede_claim`, copying `old_claim.parcel_id`
and `old_claim.person_id` onto `new_claim`. Nothing else in the function
changed. Added one assertion to
`test_correct_claim_creates_a_superseding_claim_not_an_edit_in_place`:
immediately after correcting a claim (no reprocessing in between), `GET
/parcels/{id}` must show the *new* claim's id and value — proving the
parcel link survived the correction instead of only being provable by
reading the code. Statically verified only on my end, same as the rest of
this phase — your Claude Code session's next full run is what actually
confirms it.
