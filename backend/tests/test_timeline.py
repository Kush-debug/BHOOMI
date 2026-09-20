"""
Phase 4 — timeline reconstruction (BHUMI_FORENSICS_SPEC.md §5.3/§5.4, §9 gate).

Gate, verbatim: "Timeline API returns real snapshots from real claims."

Two documents about the same parcel, years apart, with a real ownership and
area change between them -> the timeline must show two snapshots and one
material transition, computed from the actual claims those two uploads
produced (not seeded/mocked rows).
"""
import io

import pytest


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


def _upload_and_process(client, headers, filename: str, text: str, year: str):
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


# Same parcel (khasra 555/2), two documents four years apart. Deliberately
# gives both a real ownership change AND an area change so the transition
# has something concrete to detect.
DOC_2008 = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 7001
Owner Name: Ram Autar
Father Name: Shyam Autar
Khasra Number: 555/2
Area: 4.8000
Land Type: Agricultural
Remarks: timeline-2008
"""

DOC_2014 = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 7001
Owner Name: Meera Devi
Father Name: Ram Autar
Khasra Number: 555/2
Area: 3.9000
Land Type: Agricultural
Remarks: timeline-2014
"""


def test_timeline_returns_real_snapshots_and_a_material_transition(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_2008, proc_2008 = _upload_and_process(client, officer_headers, "timeline_2008.pdf", DOC_2008, "2008")
    if proc_2008.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc_2008.json()['detail']['code']}")
    assert proc_2008.status_code == 200, proc_2008.text

    doc_2014, proc_2014 = _upload_and_process(client, officer_headers, "timeline_2014.pdf", DOC_2014, "2014")
    assert proc_2014.status_code == 200, proc_2014.text

    search = client.get("/api/v1/parcels?q=555/2", headers=officer_headers).json()
    matching = [p for p in search["parcels"] if p["khasra_number"] == "555/2"]
    assert matching, f"expected the two documents to converge on one parcel, got {search}"
    parcel_id = matching[0]["id"]
    assert matching[0]["document_count"] == 2

    timeline = client.get(f"/api/v1/parcels/{parcel_id}/timeline", headers=officer_headers).json()

    years = sorted(s["as_of_year"] for s in timeline["snapshots"])
    assert years == [2008, 2014], f"expected one snapshot per document year, got {years}"

    snap_2008 = next(s for s in timeline["snapshots"] if s["as_of_year"] == 2008)
    snap_2014 = next(s for s in timeline["snapshots"] if s["as_of_year"] == 2014)
    assert snap_2008["area"] == pytest.approx(4.8)
    assert snap_2014["area"] == pytest.approx(3.9)
    # Every snapshot must actually point back to real claims, not be a
    # hollow shell — this is the literal wording of the gate.
    assert snap_2008["supporting_claim_ids"], "snapshot has no supporting claims"
    assert snap_2014["supporting_claim_ids"], "snapshot has no supporting claims"

    assert len(timeline["transitions"]) == 1
    transition = timeline["transitions"][0]
    assert transition["from_year"] == 2008
    assert transition["to_year"] == 2014
    assert transition["is_material"] is True
    assert "owner_name" in transition["changed_predicates"]
    assert "area" in transition["changed_predicates"]
    assert transition["area_delta_abs"] == pytest.approx(3.9 - 4.8)
    # Phase 5 (EventMatcher) doesn't exist yet - this must stay unset, not
    # fabricated as either matched or "unexplained".
    assert transition["explained_by_event_id"] is None


def test_timeline_of_nonexistent_parcel_is_404(client, officer_headers):
    res = client.get("/api/v1/parcels/999999/timeline", headers=officer_headers)
    assert res.status_code == 404
