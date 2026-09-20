"""Test fixtures. Every test runs against a throwaway SQLite database."""
import os
import tempfile
from pathlib import Path

import pytest

# Must be set before app.config is imported anywhere.
_TMP = Path(tempfile.mkdtemp(prefix="bhumi_test_"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-only-secret-not-used-anywhere-else")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ.setdefault("ENABLE_DEMO_SEED", "false")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from fastapi.testclient import TestClient  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.seed_data import seed_reference_data  # noqa: E402
from app.database.session import SessionLocal, engine  # noqa: E402
import app.models  # noqa: E402,F401
# Must come AFTER `import app.models`: a bare `import app.models` binds the
# name `app` in this module to the `app` PACKAGE, so if it ran after this
# line it would silently overwrite `app` (the FastAPI instance) with the
# package module, and `TestClient(app)` would fail with
# `TypeError: 'module' object is not callable`. Order matters here.
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_reference_data(db)
    finally:
        db.close()
    with TestClient(app) as c:
        yield c


def _token(client, username: str, password: str) -> str:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture(scope="session")
def officer_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'verification_officer', 'officer123')}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'superadmin', 'superadmin123')}"}


@pytest.fixture(scope="session")
def viewer_headers(client):
    return {"Authorization": f"Bearer {_token(client, 'viewer', 'viewer123')}"}


@pytest.fixture(scope="session")
def tesseract_available():
    from app.services.ocr_service import ocr_service

    return ocr_service.engine_status()["available"]
