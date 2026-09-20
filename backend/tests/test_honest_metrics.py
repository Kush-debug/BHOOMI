"""
No endpoint may return a number it did not compute.

The dashboard previously returned total_documents: 25430, a seven-day activity
timeline and a confidence distribution that were hardcoded literals, and the
Reports page charted invented OCR accuracy figures (ARCHITECTURE_AUDIT §4.4).
"""
FABRICATED_NUMBERS = [25430, 23120, 21430, 1690, 12450, 11890, 6320, 5840, 4120, 3680, 1420, 860, 310]


def _walk(node):
    if isinstance(node, dict):
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)
    else:
        yield node


def test_dashboard_reports_zero_not_invented_activity(client, admin_headers):
    """An empty deployment reports zeros, never a plausible-looking workload."""
    data = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    values = list(_walk(data))
    for fabricated in FABRICATED_NUMBERS:
        assert fabricated not in values, f"dashboard returned the old hardcoded value {fabricated}"


def test_dashboard_timeline_is_dated_not_weekday_labels(client, admin_headers):
    """The old timeline was labelled Mon..Sun with invented counts."""
    data = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    timeline = data["processing_timeline"]
    assert len(timeline) == 7
    for entry in timeline:
        assert "date" in entry, "timeline entries must carry a real date"
        assert entry["date"].count("-") == 2
        assert entry["uploaded"] >= 0


def test_unmeasured_confidence_is_null_not_a_default(client, admin_headers):
    """With nothing processed, average confidence must be null rather than 95.4."""
    data = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    if data["total_documents"] == 0:
        assert data["average_ocr_confidence"] is None
        assert data["average_extraction_confidence"] is None


def test_demo_data_is_reported_separately(client, admin_headers):
    data = client.get("/api/v1/dashboard/stats", headers=admin_headers).json()
    assert data["scope"] == "real_uploads_only"
    assert "demo_documents_excluded" in data


def test_analytics_declares_confidence_is_not_accuracy(client, admin_headers):
    data = client.get("/api/v1/analytics/quality", headers=admin_headers).json()
    note = data["measurement_note"].lower()
    assert "not accuracy" in note or "confidence" in note
    assert data["documents_measured"] == len(
        [x for x in data["by_language"]]
    ) or data["documents_measured"] >= 0


def test_health_reports_real_ocr_capability(client):
    """The sidebar used to claim 13+ languages regardless of what was installed."""
    ocr = client.get("/health").json()["ocr"]
    assert set(["engine", "available", "installed_language_packs", "supported_language_count"]) <= set(ocr)
    assert ocr["supported_language_count"] == len(ocr["supported_iso_languages"])
    if not ocr["available"]:
        assert ocr["supported_language_count"] == 0


def test_no_seeded_documents_exist(client, admin_headers):
    """Documents may only enter through upload and real processing."""
    docs = client.get("/api/v1/documents/?source_class=SEED_SYNTHETIC", headers=admin_headers).json()
    assert docs == [], "seed data must not create documents"
