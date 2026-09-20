"""
Phase 7 — officer workflow (BHUMI_FORENSICS_SPEC.md §5.9/§6, §9 Phase 7 gate).

Gate, verbatim: "End-to-end golden flow runs."

Three real workflows, each pushed through the live API (not seeded/mocked):

  1. Evidence-linked verification: correct one claim without submitting the
     whole document, and prove the correction is a superseding claim, not an
     edit in place.
  2. Resolve a finding, with a required reason, and prove the resolution
     survives reprocessing (analysis_service's reconciliation must never
     touch it again).
  3. Assign / comment / resolve an InvestigationCase, and prove RBAC keeps a
     viewer out of all three.
"""
import io

import pytest

FORBIDDEN_WORDS = ("fraud", "forgery", "forged", "illegal", "guilty", "criminal", "fake")


def _make_pdf(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 90
    for line in text.split("\n"):
        page.insert_text((60, y), line, fontsize=15)
        y += 26
    data = doc.tobytes()
    doc.close()
    return data


def _upload_and_process(client, headers, filename, text, year):
    res = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(_make_pdf(text)), "application/pdf")},
        data={
            "state": "Uttar Pradesh",
            "district": "Kanpur Nagar",
            "tehsil": "Bilhaur",
            "village": "Bilhaur Dehat",
            "document_type": "khasra_b1",
            "document_year": year,
            "language": "en",
        },
    )
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"]
    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=headers)
    return doc_id, proc


def _parcel_id(client, headers, khasra):
    search = client.get(f"/api/v1/parcels?q={khasra}", headers=headers).json()
    m = [p for p in search["parcels"] if p["khasra_number"] == khasra]
    assert m, f"no parcel for {khasra}: {search}"
    return m[0]["id"]


def _user_id(client, headers) -> int:
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"]


ROR = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: {khata}
Owner Name: {owner}
Father Name: {father}
Khasra Number: {khasra}
Area: {area}
Land Type: Agricultural
Remarks: {tag}
"""


def test_correct_claim_creates_a_superseding_claim_not_an_edit_in_place(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "441/9"
    doc_id, proc = _upload_and_process(
        client, officer_headers, "correct_a.pdf",
        ROR.format(khata="5100", owner="Prakash Chandra", father="Ram Lal", khasra=k, area="2.2000", tag="correct-a"),
        "2010",
    )
    if proc.status_code == 422:
        pytest.skip(proc.json()["detail"]["code"])
    assert proc.status_code == 200, proc.text

    claims = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()
    owner_claim = next(c for c in claims["claims"] if c["standardized_field"] == "owner_name")
    old_claim_id = owner_claim["id"]
    assert owner_claim["field_value"] == "Prakash Chandra"

    resp = client.post(
        f"/api/v1/verification/{doc_id}/claims/{old_claim_id}/correct",
        headers=officer_headers,
        json={"new_value": "Prakash Chand", "notes": "OCR misread the surname"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "success"
    new_claim = body["new_claim"]
    assert new_claim["field_value"] == "Prakash Chand"
    assert new_claim["asserted_by"] == "OFFICER"
    assert new_claim["provenance"] == "OFFICER_CORRECTION"
    assert new_claim["supersedes_claim_id"] == old_claim_id

    # the superseding claim must be visible on the parcel *immediately*,
    # with no reprocessing in between - proves parcel_id/person_id were
    # carried over from the claim it superseded, not left NULL until the
    # next IdentityResolver run
    pid = _parcel_id(client, officer_headers, k)
    parcel_claims = client.get(f"/api/v1/parcels/{pid}", headers=officer_headers).json()["claims"]
    parcel_owner_claim = next(c for c in parcel_claims if c["standardized_field"] == "owner_name")
    assert parcel_owner_claim["id"] == new_claim["id"]
    assert parcel_owner_claim["field_value"] == "Prakash Chand"

    # the correction is additive, not a mutation - both claims still exist
    full_history = client.get(
        f"/api/v1/documents/{doc_id}/claims?include_superseded=true", headers=officer_headers
    ).json()
    ids = {c["id"]: c for c in full_history["claims"]}
    assert ids[old_claim_id]["lifecycle_status"] == "SUPERSEDED"
    assert ids[new_claim["id"]]["lifecycle_status"] == "ACCEPTED"
    assert ids[old_claim_id]["field_value"] == "Prakash Chandra", "the original AI value must not be rewritten"

    # correcting to the identical current value is a documented no-op
    noop = client.post(
        f"/api/v1/verification/{doc_id}/claims/{new_claim['id']}/correct",
        headers=officer_headers,
        json={"new_value": "Prakash Chand"},
    )
    assert noop.status_code == 200
    assert noop.json()["status"] == "unchanged"

    # the now-superseded original claim id can no longer be corrected directly
    stale = client.post(
        f"/api/v1/verification/{doc_id}/claims/{old_claim_id}/correct",
        headers=officer_headers,
        json={"new_value": "Someone Else"},
    )
    assert stale.status_code == 404


def test_resolving_a_finding_requires_a_reason_and_survives_reprocessing(
    client, officer_headers, tesseract_available
):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "441/10"
    doc_a, proc_a = _upload_and_process(
        client, officer_headers, "resolve_a.pdf",
        ROR.format(khata="5200", owner="Ram Autar", father="Shyam Lal", khasra=k, area="4.8000", tag="resolve-a"),
        "2008",
    )
    if proc_a.status_code == 422:
        pytest.skip(proc_a.json()["detail"]["code"])
    assert proc_a.status_code == 200
    doc_b, proc_b = _upload_and_process(
        client, officer_headers, "resolve_b.pdf",
        ROR.format(khata="5200", owner="Meera Devi", father="Ram Autar", khasra=k, area="3.9000", tag="resolve-b"),
        "2014",
    )
    assert proc_b.status_code == 200

    pid = _parcel_id(client, officer_headers, k)
    findings = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["findings"]
    gap = next(f for f in findings if f["finding_type"] == "EVIDENCE_GAP")

    # RESOLVED without a reason is rejected - a bare status flip isn't an audit trail
    bare = client.post(
        f"/api/v1/findings/{gap['id']}/resolve", headers=officer_headers, json={"resolution_status": "RESOLVED"}
    )
    assert bare.status_code == 422

    resolved = client.post(
        f"/api/v1/findings/{gap['id']}/resolve",
        headers=officer_headers,
        json={"resolution_status": "RESOLVED", "resolution_note": "Verified against physical mutation register at tehsil office"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolution_status"] == "RESOLVED"

    # already resolved - this endpoint does not reopen findings
    again = client.post(
        f"/api/v1/findings/{gap['id']}/resolve",
        headers=officer_headers,
        json={"resolution_status": "DISMISSED", "resolution_note": "n/a"},
    )
    assert again.status_code == 409

    # reprocessing the document must not silently flip the officer's
    # resolution back to OPEN - analysis_service's is_officer_owned check
    # must hold for a finding resolved through this real endpoint
    reproc = client.post(f"/api/v1/processing/{doc_b}/start", headers=officer_headers)
    assert reproc.status_code == 200, reproc.text
    findings_after = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["findings"]
    same_gap = next(f for f in findings_after if f["id"] == gap["id"])
    assert same_gap["resolution_status"] == "RESOLVED", "reprocessing must never overwrite an officer's resolution"


def test_investigation_case_assign_comment_resolve_and_rbac(client, officer_headers, viewer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "441/11"
    _, proc_a = _upload_and_process(
        client, officer_headers, "case_a.pdf",
        ROR.format(khata="5300", owner="Ajay Kumar", father="Bishan Lal", khasra=k, area="5.0000", tag="case-a"),
        "2009",
    )
    if proc_a.status_code == 422:
        pytest.skip(proc_a.json()["detail"]["code"])
    assert proc_a.status_code == 200
    _, proc_b = _upload_and_process(
        client, officer_headers, "case_b.pdf",
        ROR.format(khata="5300", owner="Sunita Kumari", father="Ajay Kumar", khasra=k, area="4.1000", tag="case-b"),
        "2015",
    )
    assert proc_b.status_code == 200

    pid = _parcel_id(client, officer_headers, k)
    cases = client.get(f"/api/v1/investigation-cases?parcel_id={pid}", headers=officer_headers).json()
    assert cases["count"] == 1, cases
    case_id = cases["cases"][0]["id"]
    assert cases["cases"][0]["status"] == "OPEN"

    officer_id = _user_id(client, officer_headers)
    viewer_id = _user_id(client, viewer_headers)

    # RBAC: a viewer can read but not act
    assert client.post(f"/api/v1/investigation-cases/{case_id}/assign",
                        headers=viewer_headers, json={"assigned_to": officer_id}).status_code == 403
    assert client.post(f"/api/v1/investigation-cases/{case_id}/comment",
                        headers=viewer_headers, json={"text": "should not work"}).status_code == 403
    assert client.post(f"/api/v1/investigation-cases/{case_id}/resolve",
                        headers=viewer_headers, json={"resolution": "should not work"}).status_code == 403

    # a viewer cannot be assigned a case even by someone with permission
    bad_assignee = client.post(
        f"/api/v1/investigation-cases/{case_id}/assign", headers=officer_headers, json={"assigned_to": viewer_id}
    )
    assert bad_assignee.status_code == 422

    assign = client.post(
        f"/api/v1/investigation-cases/{case_id}/assign", headers=officer_headers, json={"assigned_to": officer_id}
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["assigned_to"] == officer_id
    assert assign.json()["status"] == "IN_PROGRESS", "picking up an OPEN case starts the investigation"

    comment = client.post(
        f"/api/v1/investigation-cases/{case_id}/comment", headers=officer_headers, json={"text": "Field visit scheduled."}
    )
    assert comment.status_code == 200
    comments = comment.json()["comments"]
    assert comments and comments[-1]["text"] == "Field visit scheduled."
    assert comments[-1]["author_id"] == officer_id

    resolve = client.post(
        f"/api/v1/investigation-cases/{case_id}/resolve",
        headers=officer_headers,
        json={"resolution": "Confirmed a genuine unrecorded inheritance transfer; mutation filed retroactively."},
    )
    assert resolve.status_code == 200, resolve.text
    resolved_body = resolve.json()
    assert resolved_body["status"] == "CLOSED"
    assert resolved_body["resolution"]
    blob = resolved_body["resolution"].lower()
    assert not any(w in blob for w in FORBIDDEN_WORDS), blob

    # already-closed cases refuse a second resolve
    again = client.post(
        f"/api/v1/investigation-cases/{case_id}/resolve", headers=officer_headers, json={"resolution": "again"}
    )
    assert again.status_code == 409


NO_KHASRA_DOC = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 5400
Owner Name: Deepak Verma
Father Name: Suresh Verma
Area: 3.0000
Land Type: Agricultural
Remarks: missing-khasra
"""


def test_submit_approval_never_partially_applies_when_validation_fails(client, officer_headers, tesseract_available):
    """
    A rejected /submit (missing mandatory field) must be a true no-op: the
    old bug committed `corrected_fields` via `_supersede_claim` INSIDE the
    per-field loop, which ran before the mandatory-field check further down
    - so a 422 could follow an already-durably-applied correction, with no
    VerificationRecord/audit entry for it. Validation now runs against an
    in-memory `new_state` before any claim is touched.
    """
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    # No "Khasra Number:" line at all -> khasra_number is never extracted,
    # so approval's mandatory-field check is guaranteed to fail.
    doc_id, proc = _upload_and_process(client, officer_headers, "no_khasra.pdf", NO_KHASRA_DOC, "2012")
    if proc.status_code == 422:
        pytest.skip(proc.json()["detail"]["code"])
    assert proc.status_code == 200, proc.text

    claims_before = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()["claims"]
    owner_before = next(c for c in claims_before if c["standardized_field"] == "owner_name")
    assert owner_before["field_value"] == "Deepak Verma"

    resp = client.post(
        f"/api/v1/verification/{doc_id}/submit",
        headers=officer_headers,
        json={
            "action": "approved",
            "notes": "should not apply",
            "corrected_fields": {"owner_name": "Deepak V. Corrected"},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "MISSING_MANDATORY_FIELDS"

    claims_after = client.get(
        f"/api/v1/documents/{doc_id}/claims?include_superseded=true", headers=officer_headers
    ).json()["claims"]
    owner_claims_after = [c for c in claims_after if c["standardized_field"] == "owner_name"]
    assert len(owner_claims_after) == 1, (
        "a rejected approval must not supersede any claim - found "
        f"{len(owner_claims_after)} owner_name claim(s), expected exactly the original one"
    )
    assert owner_claims_after[0]["field_value"] == "Deepak Verma"
    assert owner_claims_after[0]["lifecycle_status"] == "ACCEPTED"
    assert owner_claims_after[0]["asserted_by"] == "SYSTEM", "no officer claim should have been created"
