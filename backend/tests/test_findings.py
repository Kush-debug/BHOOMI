"""
Phase 5 — event matching + contradiction detection
(BHUMI_FORENSICS_SPEC.md §5.5 / §5.6, §9 Phase 5 gate).

Answers, through the live upload -> process path:

  1. "What event explains this change?" — a document carrying a mutation
     number explains the ownership transition it accompanies; without one,
     the material transition becomes an EVIDENCE_GAP finding.
  2. "Which changes are actually contradictory?" — two independent documents
     that disagree about the same field in the same year become a
     CONTRADICTION finding, with both claims preserved and traceable.

A finding is an investigation signal: it must never use the words fraud /
forgery / illegal, and it must carry a recommended next action.
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


ROR = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: {khata}
Owner Name: {owner}
Father Name: {father}
Khasra Number: {khasra}
Area: {area}
Land Type: Agricultural
{extra}
Remarks: {tag}
"""


def test_material_transition_without_event_becomes_an_evidence_gap(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "770/1"
    _, p1 = _upload_and_process(client, officer_headers, "gap_a.pdf",
        ROR.format(khata="8001", owner="Ram Autar", father="Shyam Lal", khasra=k, area="4.8000", extra="", tag="gap-2008"), "2008")
    if p1.status_code == 422:
        pytest.skip(p1.json()["detail"]["code"])
    assert p1.status_code == 200, p1.text
    _, p2 = _upload_and_process(client, officer_headers, "gap_b.pdf",
        ROR.format(khata="8001", owner="Meera Devi", father="Ram Autar", khasra=k, area="3.9000", extra="", tag="gap-2014"), "2014")
    assert p2.status_code == 200, p2.text

    pid = _parcel_id(client, officer_headers, k)

    findings = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["findings"]
    gaps = [f for f in findings if f["finding_type"] == "EVIDENCE_GAP"]
    assert gaps, f"expected an EVIDENCE_GAP, got {findings}"
    gap = gaps[0]
    assert gap["time_range"] == {"start": 2008, "end": 2014}
    assert "owner_name" in gap["affected_predicates"]
    assert gap["recommended_action"], "a finding must recommend a next action"
    assert gap["resolution_status"] == "OPEN"
    blob = (gap["explanation"] + gap["recommended_action"]).lower()
    assert not any(w in blob for w in FORBIDDEN_WORDS), blob

    # the transition itself stays unexplained (no fabricated event id)
    timeline = client.get(f"/api/v1/parcels/{pid}/timeline", headers=officer_headers).json()
    assert timeline["transitions"][0]["explained_by_event_id"] is None


def test_mutation_document_explains_the_transition_and_closes_the_gap(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "770/2"
    _, p1 = _upload_and_process(client, officer_headers, "exp_a.pdf",
        ROR.format(khata="8100", owner="Ram Autar", father="Shyam Lal", khasra=k, area="4.8000", extra="", tag="exp-2008"), "2008")
    if p1.status_code == 422:
        pytest.skip(p1.json()["detail"]["code"])
    assert p1.status_code == 200
    # 2014 document carries the mutation order number that records the transfer.
    _, p2 = _upload_and_process(client, officer_headers, "exp_b.pdf",
        ROR.format(khata="8100", owner="Meera Devi", father="Ram Autar", khasra=k, area="4.8000",
                   extra="Mutation Number: M-4471", tag="exp-2014"), "2014")
    assert p2.status_code == 200, p2.text

    pid = _parcel_id(client, officer_headers, k)

    events = client.get(f"/api/v1/parcels/{pid}/events", headers=officer_headers).json()["events"]
    assert any(e["event_type"] == "MUTATION" and e["order_number"] == "M-4471" for e in events), events

    timeline = client.get(f"/api/v1/parcels/{pid}/timeline", headers=officer_headers).json()
    t = timeline["transitions"][0]
    assert t["is_material"] is True
    assert t["explained_by_event_id"] is not None, "the mutation event should explain this transition"

    findings = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["findings"]
    assert not [f for f in findings if f["finding_type"] == "EVIDENCE_GAP"], findings


def test_conflicting_claims_same_year_become_a_traceable_contradiction(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "770/3"
    d1, p1 = _upload_and_process(client, officer_headers, "conf_a.pdf",
        ROR.format(khata="8200", owner="Suresh Kumar", father="Mohan Lal", khasra=k, area="2.5000", extra="", tag="conf-a"), "2010")
    if p1.status_code == 422:
        pytest.skip(p1.json()["detail"]["code"])
    assert p1.status_code == 200
    d2, p2 = _upload_and_process(client, officer_headers, "conf_b.pdf",
        ROR.format(khata="8200", owner="Rakesh Kumar", father="Mohan Lal", khasra=k, area="2.5000", extra="", tag="conf-b"), "2010")
    assert p2.status_code == 200, p2.text

    pid = _parcel_id(client, officer_headers, k)

    findings = client.get("/api/v1/findings?type=CONTRADICTION&parcel_id=%d" % pid, headers=officer_headers).json()["findings"]
    assert findings, "expected a CONTRADICTION finding"
    c = findings[0]
    assert c["finding_type"] == "CONTRADICTION"
    assert "owner_name" in c["affected_predicates"]
    assert set(c["source_document_ids"]) == {d1, d2}, c
    assert len(c["source_claim_ids"]) >= 2

    # both conflicting claims still exist and are ACCEPTED (nothing discarded)
    for doc_id in (d1, d2):
        claims = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()["claims"]
        owners = [cl for cl in claims if cl["standardized_field"] == "owner_name"]
        assert len(owners) == 1 and owners[0]["lifecycle_status"] == "ACCEPTED"

    detail = client.get(f"/api/v1/findings/{c['id']}", headers=officer_headers).json()
    assert len(detail["source_documents"]) == 2
    blob = (detail["explanation"] + (detail["recommended_action"] or "")).lower()
    assert not any(w in blob for w in FORBIDDEN_WORDS), blob


def test_findings_endpoint_requires_auth(client):
    assert client.get("/api/v1/findings").status_code in (401, 403)


def test_reprocessing_does_not_duplicate_findings(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    k = "770/4"
    d1, p1 = _upload_and_process(client, officer_headers, "dup_a.pdf",
        ROR.format(khata="8300", owner="Ram Autar", father="X", khasra=k, area="4.8000", extra="", tag="dup-a"), "2008")
    if p1.status_code == 422:
        pytest.skip(p1.json()["detail"]["code"])
    d2, p2 = _upload_and_process(client, officer_headers, "dup_b.pdf",
        ROR.format(khata="8300", owner="Meera Devi", father="Y", khasra=k, area="3.9000", extra="", tag="dup-b"), "2014")
    assert p2.status_code == 200

    pid = _parcel_id(client, officer_headers, k)
    before = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["count"]
    assert before >= 1

    r = client.post(f"/api/v1/processing/{d2}/start", headers=officer_headers)
    assert r.status_code == 200, r.text
    after = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["count"]
    assert after == before, f"reprocessing changed finding count {before} -> {after}"
