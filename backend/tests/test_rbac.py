"""
Access control.

Before Phase 1, 30 of 45 endpoints were fully public, including bulk registry
export, the audit trail, document downloads and anomaly resolution
(ARCHITECTURE_AUDIT §4.3).
"""
import pytest

# (method, path) pairs that must reject an unauthenticated caller.
PROTECTED = [
    ("get", "/api/v1/documents/"),
    ("get", "/api/v1/documents/1"),
    ("get", "/api/v1/documents/1/file"),
    ("get", "/api/v1/documents/1/pages/1"),
    ("get", "/api/v1/records/"),
    ("get", "/api/v1/records/export/csv"),
    ("get", "/api/v1/audit/logs"),
    ("get", "/api/v1/validation/anomalies"),
    ("get", "/api/v1/dashboard/stats"),
    ("get", "/api/v1/analytics/quality"),
    ("get", "/api/v1/analytics/throughput"),
    ("get", "/api/v1/verification/queue"),
    ("get", "/api/v1/gis/parcels"),
    ("get", "/api/v1/learning/corrections"),
    ("get", "/api/v1/learning/terminology"),
    ("get", "/api/v1/locations/states"),
    ("get", "/api/v1/processing/1/pipeline-status"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_endpoint_requires_authentication(client, method, path):
    res = getattr(client, method)(path)
    assert res.status_code in (401, 403), f"{method.upper()} {path} responded {res.status_code}"


def test_public_endpoints_stay_public(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_viewer_cannot_export_the_registry(client, viewer_headers):
    res = client.get("/api/v1/records/export/csv", headers=viewer_headers)
    assert res.status_code == 403


def test_viewer_cannot_read_the_audit_trail(client, viewer_headers):
    assert client.get("/api/v1/audit/logs", headers=viewer_headers).status_code == 403


def test_viewer_cannot_read_uploaded_documents(client, viewer_headers):
    assert client.get("/api/v1/documents/", headers=viewer_headers).status_code == 403


def test_viewer_cannot_resolve_a_finding(client, viewer_headers):
    res = client.put(
        "/api/v1/validation/resolve/1", headers=viewer_headers, params={"reason": "test"}
    )
    assert res.status_code == 403


def test_viewer_cannot_approve_a_record(client, viewer_headers):
    res = client.post(
        "/api/v1/verification/1/submit",
        headers=viewer_headers,
        json={"action": "approved", "corrected_fields": {}, "notes": "n/a"},
    )
    assert res.status_code == 403, "a public viewer must never be able to verify a land record"


def test_officer_cannot_administer_users(client, officer_headers):
    assert client.get("/api/v1/admin/users", headers=officer_headers).status_code == 403


def test_officer_can_read_documents(client, officer_headers):
    assert client.get("/api/v1/documents/", headers=officer_headers).status_code == 200


def test_resolving_a_finding_requires_a_reason(client, officer_headers):
    res = client.put("/api/v1/validation/resolve/1", headers=officer_headers)
    assert res.status_code == 422, "resolution must require a recorded reason"
