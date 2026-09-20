"""Reference data still seeds correctly after the demo-document removal."""


def test_all_states_and_uts_present(client, admin_headers):
    states = client.get("/api/v1/locations/states", headers=admin_headers).json()
    assert len(states) == 36  # 28 states + 8 union territories


def test_location_hierarchy_cascades(client, admin_headers):
    states = client.get("/api/v1/locations/states", headers=admin_headers).json()
    tn = next(s for s in states if s["name"] == "Tamil Nadu")
    districts = client.get(
        f"/api/v1/locations/states/{tn['id']}/districts", headers=admin_headers
    ).json()
    cbe = next(d for d in districts if d["name"] == "Coimbatore")
    tehsils = client.get(
        f"/api/v1/locations/districts/{cbe['id']}/tehsils", headers=admin_headers
    ).json()
    pollachi = next(t for t in tehsils if t["name"] == "Pollachi")
    villages = client.get(
        f"/api/v1/locations/tehsils/{pollachi['id']}/villages", headers=admin_headers
    ).json()
    assert any(v["name"] == "Anamalai" for v in villages)


def test_admin_crud_and_deactivation_still_work(client, admin_headers):
    created = client.post(
        "/api/v1/admin/users",
        headers=admin_headers,
        json={
            "username": "phase1_test_officer",
            "email": "phase1.test@karnataka.gov.in",
            "password": "phase1testpass123",
            "full_name": "Test Officer",
            "role": "tehsil_officer",
            "state": "Karnataka",
            "district": "Bengaluru Rural",
            "tehsil": "Nelamangala",
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "phase1_test_officer", "password": "phase1testpass123"},
        ).status_code
        == 200
    )

    client.put(f"/api/v1/admin/users/{user_id}/status", headers=admin_headers, json={"is_active": False})
    blocked = client.post(
        "/api/v1/auth/login", json={"username": "phase1_test_officer", "password": "phase1testpass123"}
    )
    assert blocked.status_code == 403

    client.delete(f"/api/v1/admin/users/{user_id}", headers=admin_headers)


def test_secret_key_is_not_the_old_hardcoded_literal():
    from app.config import settings

    assert settings.SECRET_KEY
    assert "bhoomi-secret-key-super-secure-key-2026-gov-nic" != settings.SECRET_KEY


def test_wildcard_cors_is_rejected_in_production():
    import pytest

    from app.config import Settings

    s = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 40, CORS_ORIGINS="*")
    with pytest.raises(ValueError):
        s.cors_origin_list()
