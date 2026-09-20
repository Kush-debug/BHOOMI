"""
Phase 6 — evidence sufficiency + prioritisation (BHUMI_FORENSICS_SPEC.md
§5.7 / §5.9, §9 Phase 6 gate).

Gate, verbatim: "Score breakdown visible and reproducible."

Pushes two real documents through the live upload -> process path (same
corpus shape as test_findings.py's evidence-gap case: an owner+area change
between 2008 and 2014 with no mutation number, so it produces exactly one
OPEN, CRITICAL EVIDENCE_GAP finding) and checks that:

  1. GET /parcels/{id}/sufficiency returns all six components, each
     honestly marked available or not - never a fabricated number in place
     of "not available" (spatial_consistency has no surveyed geometry to
     compare against, so it must report unavailable, not a guessed score).
  2. The resulting Finding actually has evidence_sufficiency populated
     (NULL through Phase 5, real as of Phase 6).
  3. An InvestigationCase exists for the parcel with a deterministic
     priority_score/band and a term-by-term breakdown that explains it.
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
Remarks: {tag}
"""

_ALL_COMPONENTS = {
    "extraction_quality",
    "cross_document_agreement",
    "temporal_continuity",
    "event_evidence",
    "identity_confidence",
    "spatial_consistency",
}


def _setup_gap_parcel(client, officer_headers):
    k = "910/3"
    _, p1 = _upload_and_process(
        client, officer_headers, "score_a.pdf",
        ROR.format(khata="9200", owner="Ram Autar", father="Shyam Lal", khasra=k, area="4.8000", tag="score-2008"),
        "2008",
    )
    if p1.status_code == 422:
        pytest.skip(p1.json()["detail"]["code"])
    assert p1.status_code == 200, p1.text
    _, p2 = _upload_and_process(
        client, officer_headers, "score_b.pdf",
        ROR.format(khata="9200", owner="Meera Devi", father="Ram Autar", khasra=k, area="3.9000", tag="score-2014"),
        "2014",
    )
    assert p2.status_code == 200, p2.text
    return _parcel_id(client, officer_headers, k)


def test_sufficiency_breakdown_is_complete_and_honest_about_gaps(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    pid = _setup_gap_parcel(client, officer_headers)

    resp = client.get(f"/api/v1/parcels/{pid}/sufficiency", headers=officer_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["scope_type"] == "PARCEL"
    assert body["scope_id"] == pid
    assert set(body["components"].keys()) == _ALL_COMPONENTS

    # extraction_quality: two real documents were OCR'd, so this must be a
    # real, available number in [0, 1] - not a placeholder.
    eq = body["components"]["extraction_quality"]
    assert eq["available"] is True
    assert 0.0 <= eq["value"] <= 1.0

    # identity_confidence: both documents resolved onto the same parcel via
    # an exact khasra match (no separator variation in this corpus) -> 1.0.
    idc = body["components"]["identity_confidence"]
    assert idc["available"] is True
    assert idc["value"] == 1.0

    # spatial_consistency: no GISParcel with source_class=SURVEYED exists
    # for this parcel - must be honestly unavailable, never a fabricated
    # comparison (BHUMI_FORENSICS_SPEC.md §5.7).
    spatial = body["components"]["spatial_consistency"]
    assert spatial["available"] is False
    assert spatial["value"] is None
    assert spatial["basis"], "an unavailable component must still say why"

    # event_evidence: one material transition (owner+area changed), no
    # mutation number anywhere in the corpus -> 0 matched / 1 material.
    ev = body["components"]["event_evidence"]
    assert ev["available"] is True
    assert ev["value"] == 0.0

    # overall_score is renormalised over whatever was available, not a
    # simple average that silently treats "unavailable" as zero.
    assert body["overall_score"] is not None
    assert 0.0 <= body["overall_score"] <= 1.0
    assert body["formula_version"]


def test_finding_evidence_sufficiency_is_populated_after_scoring(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    pid = _setup_gap_parcel(client, officer_headers)

    findings = client.get(f"/api/v1/parcels/{pid}/findings", headers=officer_headers).json()["findings"]
    gaps = [f for f in findings if f["finding_type"] == "EVIDENCE_GAP"]
    assert gaps, findings

    # /parcels/{id}/findings doesn't project evidence_sufficiency (it didn't
    # exist when that endpoint was written in Phase 5) - check via the
    # /findings/{id} detail endpoint, which does.
    detail = client.get(f"/api/v1/findings/{gaps[0]['id']}", headers=officer_headers).json()
    assert detail["evidence_sufficiency"] is not None, "Phase 6 must populate this - Phase 5 left it NULL"
    assert 0.0 <= detail["evidence_sufficiency"] <= 1.0


def test_investigation_case_is_created_with_explainable_priority(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract not installed")
    pid = _setup_gap_parcel(client, officer_headers)

    resp = client.get(f"/api/v1/investigation-cases?parcel_id={pid}", headers=officer_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] == 1, body
    case = body["cases"][0]

    assert case["parcel_id"] == pid
    assert case["finding_ids"], "a case must actually reference the findings it was raised for"
    assert case["priority_score"] is not None
    assert case["priority_band"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert case["status"] == "OPEN"
    assert case["assigned_to"] is None  # Phase 7 territory - nothing assigns automatically

    # the breakdown must actually justify the number, not just assert one
    breakdown = case["priority_breakdown"]
    assert breakdown["score"] == case["priority_score"]
    terms = breakdown["terms"]
    assert set(terms.keys()) == {"severity", "evidence_gap", "ownership_involved", "area_magnitude", "staleness"}
    assert terms["severity"]["available"] is True
    assert terms["ownership_involved"]["value"] == 1.0  # owner_name is in this finding's affected_predicates

    # case detail endpoint round-trips to the same findings
    case_detail = client.get(f"/api/v1/investigation-cases/{case['id']}", headers=officer_headers).json()
    assert case_detail["parcel"]["khasra_number"] == "910/3"
    assert any(f["finding_type"] == "EVIDENCE_GAP" for f in case_detail["findings"])
    blob = " ".join(f["explanation"] for f in case_detail["findings"]).lower()
    assert not any(w in blob for w in FORBIDDEN_WORDS), blob
