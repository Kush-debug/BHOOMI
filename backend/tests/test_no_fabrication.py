"""
The tests that matter most.

Background: the pipeline used to contain an OCR engine that ignored the uploaded
file and returned hand-written land-record text with hand-written bounding boxes
and confidences of 0.94-0.99. It fired whenever Tesseract was unavailable or
returned short output. A resume uploaded to the running system produced a Tamil
Patta extract naming an owner, a survey number and a registration deed number
(ARCHITECTURE_AUDIT §4.1).

These tests exist so that can never come back silently.
"""
import io

import pytest

# Values the deleted engine used to invent. None of them may ever appear in the
# output of processing a document that does not contain them.
FABRICATED_MARKERS = [
    "Ram Prasad", "राम प्रसाद", "Shyam Sundar", "श्याम सुंदर",
    "Ramasamy", "ராமசாமி", "Murugan", "முருகன்",
    "Venkateswarlu", "వెంకటేశ్వర్లు", "Manjunath", "ಮಂಜುನಾಥ್",
    "Suresh Kumar", "सुरेश कुमार",
    "TN-REG-2023-4512", "UP-REG-2023-7819", "AP-MUT-2023-1104", "MR-2023-0095",
    "MUT-2023/892", "नामांतरण-2023/892",
    "REVENUE DEPARTMENT - GOVERNMENT OF INDIA",
    "வருவாய்த் துறை", "రెవెన్యూ శాఖ", "ಕಂದಾಯ ಇಲಾಖೆ",
    "उद्धरण खतौनी", "खसरा (प्रपत्र बी-1",
]


def test_fabricating_engine_class_is_gone():
    """The class itself must not exist, under any name, in the OCR module."""
    import inspect

    from app.services import ocr_service as module

    assert not hasattr(module, "HybridIndicOCREngine")

    source = inspect.getsource(module)
    engine_classes = [
        name
        for name, obj in vars(module).items()
        if inspect.isclass(obj) and name.endswith("Engine")
    ]
    assert set(engine_classes) == {"BaseOCREngine", "TesseractEngine"}, engine_classes

    # No land-record vocabulary may be embedded in the OCR module at all: there is
    # nothing legitimate for an OCR engine to hardcode about revenue documents.
    for marker in ["खसरा संख्या", "उरிமையாளர்"[:6], "Khata Number:", "Landholder"]:
        assert marker not in source, f"OCR module still contains land-record text: {marker!r}"


def test_ocr_raises_on_missing_image():
    """A missing page must raise, not return plausible text."""
    from app.core.errors import OcrEmptyResultError, OcrEngineUnavailableError
    from app.services.ocr_service import ocr_service

    with pytest.raises((OcrEmptyResultError, OcrEngineUnavailableError)):
        ocr_service.process_page("/nonexistent/path/page_1.png", page_number=1)


def test_ocr_service_has_no_fallback_engine():
    """process_page must dispatch to exactly one engine with no except-fallback."""
    import inspect

    from app.services.ocr_service import OCRService

    source = inspect.getsource(OCRService)
    assert "except" not in source, (
        "OCRService swallows an exception somewhere. Any except here risks "
        "reintroducing a silent fallback."
    )


def _make_pdf(text: str) -> bytes:
    """Render a real PDF containing the given text, at a size Tesseract can read."""
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


NON_LAND_DOCUMENT = """CURRICULUM VITAE
Priya Raghavan
Senior Backend Engineer

EXPERIENCE
2021 to present  Payments platform, Bengaluru
2018 to 2021     Logistics scheduling systems

EDUCATION
B.Tech Computer Science

SKILLS
Python, Go, PostgreSQL, distributed systems
"""


def test_non_land_document_is_rejected_not_invented(client, officer_headers, tesseract_available):
    """THE critical test.

    Upload a document that is definitively not a land record. The system must
    report that it found no land-record fields. It must not produce an owner, a
    khasra number, an area, or any of the values the deleted engine used to
    invent.
    """
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    res = _upload(client, officer_headers, "curriculum_vitae.pdf", _make_pdf(NON_LAND_DOCUMENT))
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"]

    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)

    # Correct behaviour is an explicit failure.
    assert proc.status_code == 422, (
        f"Expected the pipeline to reject a non-land-record document, got "
        f"{proc.status_code}: {proc.text[:400]}"
    )
    detail = proc.json()["detail"]
    assert detail["code"] in ("NO_LAND_RECORD_FIELDS_FOUND", "OCR_EMPTY_RESULT")

    # And the document must be marked failed with the real reason, holding no fields.
    doc = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    assert doc["status"] == "failed"
    assert doc["processing_error_code"] == detail["code"]
    assert doc["extracted_fields"] == []

    blob = (doc.get("original_ocr_text") or "") + str(doc.get("extracted_fields"))
    for marker in FABRICATED_MARKERS:
        assert marker not in blob, f"Fabricated value {marker!r} appeared for a CV upload"


LAND_DOCUMENT = """RECORD OF RIGHTS - REVENUE EXTRACT
District: Kanpur Nagar   Tehsil: Bilhaur   Village: Bilhaur Dehat
Khata Number: 7781
Owner Name: Kavita Deshmukh
Father Name: Anil Deshmukh
Khasra Number: 903/2
Area: 2.3400
Land Type: Agricultural
"""


def test_real_land_document_extracts_its_own_values(client, officer_headers, tesseract_available):
    """Values must come from the uploaded file, not from seed or demo data.

    The identifiers below (7781, 903/2, Kavita Deshmukh, 2.34) exist nowhere in
    the seed data, so anything that reads them back must have read this document.
    """
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    res = _upload(client, officer_headers, "ror_903_2.pdf", _make_pdf(LAND_DOCUMENT))
    assert res.status_code == 200, res.text
    doc_id = res.json()["id"]

    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)
    if proc.status_code == 422:
        pytest.skip(f"OCR quality too low in this environment: {proc.json()['detail']['code']}")
    assert proc.status_code == 200, proc.text

    doc = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    ocr_text = doc["original_ocr_text"] or ""

    for marker in FABRICATED_MARKERS:
        assert marker not in ocr_text, f"Fabricated value {marker!r} leaked into OCR output"

    # At least one identifier unique to this file must have been read back.
    assert any(token in ocr_text for token in ("903", "7781", "Deshmukh", "Kavita")), (
        f"None of the document's own identifiers appear in the OCR output: {ocr_text[:300]!r}"
    )

    fields = {f["standardized_field"]: f for f in doc["extracted_fields"]}
    assert fields, "no fields extracted from a document that clearly contains them"

    # Every document-sourced field is either grounded in OCR geometry or honestly
    # declares that it has none. No placeholder boxes.
    placeholder_boxes = [
        {"x": 60, "y": 200, "w": 250, "h": 35},
        {"x": 50, "y": 140, "w": 300, "h": 35},
        {"x": 50, "y": 85, "w": 300, "h": 25},
    ]
    for name, field in fields.items():
        if field["bbox_source"] == "NONE":
            assert field["bounding_box"] is None, f"{name} claims no region but carries a box"
        else:
            assert field["bounding_box"] is not None
            assert field["bounding_box"] not in placeholder_boxes, f"{name} has a placeholder box"


def test_upload_metadata_fields_are_labelled_not_claimed_as_extraction(
    client, officer_headers, tesseract_available
):
    """Location values typed on the upload form must not pose as document extraction."""
    if not tesseract_available:
        pytest.skip("tesseract is not installed in this environment")

    res = _upload(client, officer_headers, "ror_meta.pdf", _make_pdf(LAND_DOCUMENT + "\nSurvey: 41"))
    assert res.status_code == 200
    doc_id = res.json()["id"]
    proc = client.post(f"/api/v1/processing/{doc_id}/start", headers=officer_headers)
    if proc.status_code == 422:
        pytest.skip("OCR quality too low in this environment")

    doc = client.get(f"/api/v1/documents/{doc_id}", headers=officer_headers).json()
    for field in doc["extracted_fields"]:
        if field["provenance"] == "UPLOAD_METADATA":
            assert field["confidence"] is None, "form metadata must not carry a confidence score"
            assert field["bounding_box"] is None
            assert field["bbox_source"] == "NONE"
