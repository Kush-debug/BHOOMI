"""
Phase 2 — evidence foundation (BHUMI_FORENSICS_SPEC.md §3.1).

These tests exist to prove three specific claims:

1. Every OCR word Tesseract found is persisted as its own EvidenceRegion row,
   not just the words that happened to match an extracted value.
2. Reprocessing a document supersedes its old claims instead of deleting them
   — both the old and new values stay queryable.
3. An officer correction creates a new claim (asserted_by=OFFICER) that
   supersedes the AI one, and a later reprocess never overwrites it.
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


def _upload(client, headers, filename: str, content: bytes):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
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


LAND_DOCUMENT_TEMPLATE = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 5510
Owner Name: Meera Iyer
Father Name: Ganesh Iyer
Khasra Number: 211/3
Area: 1.8500
Land Type: Agricultural
Remarks: test-doc-{tag}
"""
# Upload dedups by SHA-256 of the file content, so every test that uploads a
# document needs distinct bytes — the trailing Remarks line is what varies.


def _land_document(tag: str) -> str:
    return LAND_DOCUMENT_TEMPLATE.format(tag=tag)


def _upload_and_process(client, headers, filename: str, text: str):
    res = _upload(client, headers, filename, _make_pdf(text))
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"]
    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=headers)
    return doc_id, proc


def test_every_ocr_word_becomes_a_region(client, officer_headers, tesseract_available):
    """The regions endpoint must expose the FULL OCR output, not just the
    handful of words that matched an extracted field."""
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_id, proc = _upload_and_process(client, officer_headers, "regions_211_3.pdf", _land_document("regions"))
    if proc.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc.json()['detail']['code']}")
    assert proc.status_code == 200, proc.text

    regions = client.get(f"/api/v1/documents/{doc_id}/regions", headers=officer_headers).json()
    claims = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()

    assert regions["count"] > claims["count"], (
        "expected far more OCR word regions than extracted claims — the document "
        "has headings, labels and punctuation that are not land-record fields but "
        "must still be persisted as evidence"
    )
    for r in regions["regions"]:
        assert r["bbox"] and all(k in r["bbox"] for k in ("x", "y", "w", "h"))
        assert r["geometry_source"] == "OCR_WORD_BOX"


def test_claim_evidence_endpoint_walks_back_to_a_real_region(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_id, proc = _upload_and_process(client, officer_headers, "evidence_211_3.pdf", _land_document("evidence"))
    if proc.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc.json()['detail']['code']}")
    assert proc.status_code == 200, proc.text

    claims = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()["claims"]
    grounded = [c for c in claims if c["bbox_source"] == "OCR_WORD_BOX"]
    assert grounded, "expected at least one field grounded in real OCR geometry"

    evidence = client.get(f"/api/v1/claims/{grounded[0]['id']}/evidence", headers=officer_headers).json()
    assert evidence["evidence_available"] is True
    assert evidence["evidence_region"] is not None
    assert evidence["ocr_run"] is not None
    assert evidence["document"]["id"] == doc_id


def test_reprocessing_supersedes_instead_of_deleting(client, officer_headers, tesseract_available):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    res = _upload(client, officer_headers, "supersede_211_3.pdf", _make_pdf(_land_document("supersede")))
    assert res.status_code == 200
    doc_id = res.json()["id"]

    proc1 = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)
    if proc1.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc1.json()['detail']['code']}")
    assert proc1.status_code == 200, proc1.text

    doc_v1 = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    owner_v1 = next(f for f in doc_v1["extracted_fields"] if f["standardized_field"] == "owner_name")
    assert "Meera" in (owner_v1["field_value"] or "")

    # Re-upload the SAME document id's file isn't possible via this API (each
    # upload is a new document), so reprocessing here re-runs the pipeline on
    # the same stored file, which yields the same OCR text — this test proves
    # the *mechanism* (old claim -> SUPERSEDED, new claim -> ACCEPTED, same
    # value) via a second /process call, not a changed document.
    proc2 = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)
    assert proc2.status_code == 200, proc2.text

    all_claims = client.get(
        f"/api/v1/documents/{doc_id}/claims?include_superseded=true", headers=officer_headers
    ).json()["claims"]
    owner_claims = [c for c in all_claims if c["standardized_field"] == "owner_name"]
    assert len(owner_claims) >= 2, "reprocessing must add a new claim, not overwrite the old one"
    assert sum(1 for c in owner_claims if c["lifecycle_status"] == "ACCEPTED") == 1
    assert any(c["lifecycle_status"] == "SUPERSEDED" for c in owner_claims)

    current = client.get(f"/api/v1/documents/{doc_id}/claims", headers=officer_headers).json()["claims"]
    assert sum(1 for c in current if c["standardized_field"] == "owner_name") == 1, (
        "the current-claims view must show exactly one owner_name, not the full history"
    )


def test_officer_correction_supersedes_and_survives_reprocessing(
    client, officer_headers, admin_headers, tesseract_available
):
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    doc_id, proc = _upload_and_process(client, officer_headers, "officer_edit_211_3.pdf", _land_document("officeredit"))
    if proc.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc.json()['detail']['code']}")
    assert proc.status_code == 200, proc.text

    doc = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    fields = {f["standardized_field"]: f for f in doc["extracted_fields"]}
    assert "owner_name" in fields

    submit = client.post(
        f"/api/v1/verification/{doc_id}/submit",
        headers=admin_headers,
        json={
            "action": "edited_approved",
            "notes": "corrected owner spelling",
            "corrected_fields": {
                "owner_name": "Meera Iyer (Corrected)",
                "khasra_number": fields["khasra_number"]["field_value"],
                "khata_number": fields["khata_number"]["field_value"],
                "area": fields["area"]["field_value"],
            },
        },
    )
    assert submit.status_code == 200, submit.text

    all_claims = client.get(
        f"/api/v1/documents/{doc_id}/claims?include_superseded=true", headers=officer_headers
    ).json()["claims"]
    owner_claims = sorted(
        (c for c in all_claims if c["standardized_field"] == "owner_name"),
        key=lambda c: c["id"],
    )
    assert len(owner_claims) == 2
    ai_claim, officer_claim = owner_claims
    assert ai_claim["lifecycle_status"] == "SUPERSEDED"
    assert officer_claim["lifecycle_status"] == "ACCEPTED"
    assert officer_claim["asserted_by"] == "OFFICER"
    assert officer_claim["provenance"] == "OFFICER_CORRECTION"
    assert officer_claim["confidence"] is None
    assert officer_claim["supersedes_claim_id"] == ai_claim["id"]

    # Reprocessing must not silently overwrite the officer's value.
    proc2 = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)
    assert proc2.status_code == 200, proc2.text

    doc_after = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    owner_after = next(f for f in doc_after["extracted_fields"] if f["standardized_field"] == "owner_name")
    assert owner_after["field_value"] == "Meera Iyer (Corrected)"
    assert owner_after["asserted_by"] == "OFFICER"
