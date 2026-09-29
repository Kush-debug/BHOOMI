"""
Phase 3 — parcel identity (BHUMI_FORENSICS_SPEC.md §3.2, §9 Phase 3 gate).

The gate, verbatim: "Two documents about one Khasra converge on one parcel."
These tests prove that, and its converse (a different khasra number does NOT
converge), using two independently-generated real PDFs pushed through the
live upload -> process path — not seeded rows.
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


def _upload_and_process(client, headers, filename: str, text: str):
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
            "document_year": "2024",
            "language": "en",
        },
    )
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"]
    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=headers)
    return doc_id, proc


# Same parcel (khasra 340/1, same village), two independent documents years
# apart, deliberately different raw khasra spelling ("340-1" vs "340/1") to
# also prove separator normalisation converges them.
DOC_A = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 9012
Owner Name: Suman Tripathi
Father Name: Om Tripathi
Khasra Number: 340-1
Area: 2.1000
Land Type: Agricultural
Remarks: converge-a
"""

DOC_B = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 9012
Owner Name: Suman   Tripathi
Father Name: Om Tripathi
Khasra Number: 340/1
Area: 1.9500
Land Type: Agricultural
Remarks: converge-b
"""

# Different parcel entirely (different khasra number, same village).
DOC_C = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 9013
Owner Name: Deepak Rathore
Father Name: Vinod Rathore
Khasra Number: 118/5
Area: 0.8000
Land Type: Agricultural
Remarks: distinct-c
"""


def test_two_documents_same_khasra_converge_on_one_parcel(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_a, proc_a = _upload_and_process(client, officer_headers, "parcel_a.pdf", DOC_A)
    if proc_a.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc_a.json()['detail']['code']}")
    assert proc_a.status_code == 200, proc_a.text

    doc_b, proc_b = _upload_and_process(client, officer_headers, "parcel_b.pdf", DOC_B)
    assert proc_b.status_code == 200, proc_b.text

    # The /documents/{id}/claims schema doesn't expose parcel_id (Phase 2's
    # schema wasn't extended for it), so convergence is verified through the
    # /parcels endpoint instead, which is the actual Phase 3 gate surface.
    search = client.get("/api/v1/parcels?q=340/1", headers=officer_headers).json()
    assert search["count"] >= 1, search

    matching = [p for p in search["parcels"] if p["khasra_number"] == "340/1"]
    assert matching, f"expected a parcel normalised to '340/1', got {[p['khasra_number'] for p in search['parcels']]}"
    parcel = matching[0]
    assert parcel["document_count"] == 2, (
        f"expected both documents to converge on one parcel, got document_count={parcel['document_count']}"
    )

    detail = client.get(f"/api/v1/parcels/{parcel['id']}", headers=officer_headers).json()
    assert {d["id"] for d in detail["documents"]} == {doc_a, doc_b}

    # Same owner, minor whitespace variation across the two documents ->
    # one Person, not two.
    person_ids = {c["person_id"] for c in detail["claims"] if c["standardized_field"] == "owner_name"}
    assert len(person_ids) == 1 and None not in person_ids, (
        f"expected the two owner_name claims to resolve to one Person, got {person_ids}"
    )


def test_different_khasra_creates_a_distinct_parcel(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_a, proc_a = _upload_and_process(client, officer_headers, "parcel_conv_a.pdf", DOC_A)
    if proc_a.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc_a.json()['detail']['code']}")
    assert proc_a.status_code == 200

    doc_c, proc_c = _upload_and_process(client, officer_headers, "parcel_c.pdf", DOC_C)
    assert proc_c.status_code == 200, proc_c.text

    search_a = client.get("/api/v1/parcels?q=340/1", headers=officer_headers).json()
    search_c = client.get("/api/v1/parcels?q=118/5", headers=officer_headers).json()

    ids_a = {p["id"] for p in search_a["parcels"] if p["khasra_number"] == "340/1"}
    ids_c = {p["id"] for p in search_c["parcels"] if p["khasra_number"] == "118/5"}
    assert ids_a and ids_c
    assert ids_a.isdisjoint(ids_c), "a different khasra number must not resolve to the same parcel"
