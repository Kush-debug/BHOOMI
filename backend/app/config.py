"""
Application settings.

All secrets and environment-dependent values come from the environment or a local
.env file. Nothing security-relevant is hardcoded (see ARCHITECTURE_AUDIT §4.8).
"""
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
_DEV_SECRET_FILE = BASE_DIR / ".dev_secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -- identity -----------------------------------------------------------
    PROJECT_NAME: str = "Bhumi Forensics - Evidence-Backed Land Record Intelligence"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production

    # -- security -----------------------------------------------------------
    # Never defaulted to a literal. Production refuses to start without it;
    # development generates a machine-local key stored outside source control.
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8h, down from 24h

    # Comma-separated in the environment, e.g. "http://localhost:5173,https://bhumi.gov.in"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # -- database -----------------------------------------------------------
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/bhoomi_land_records.db"

    # -- storage ------------------------------------------------------------
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    DEMO_CORPUS_DIR: Path = BASE_DIR / "data" / "demo_corpus"
    MAX_UPLOAD_MB: int = 25

    # -- seeding ------------------------------------------------------------
    # Geography, users and the mock master registry are always seeded (they are
    # reference data). Synthetic demo *documents* and GIS parcels are opt-in and
    # are tagged SEED_SYNTHETIC so they never masquerade as real records.
    ENABLE_DEMO_SEED: bool = True
    SEED_DEFAULT_PASSWORD: str = ""  # required when seeding users outside development

    # -- OCR ----------------------------------------------------------------
    OCR_ENGINE: str = "tesseract"
    # ISO codes, comma separated. Only packs actually installed are ever requested.
    OCR_LANGUAGES: str = "en,hi,ta,te,kn"
    OCR_TWO_PASS: bool = True
    OCR_MIN_CHARS: int = 20  # below this, OCR_EMPTY_RESULT is raised

    # -- extraction / confidence -------------------------------------------
    CONFIDENCE_HIGH_THRESHOLD: float = 0.90
    CONFIDENCE_MEDIUM_THRESHOLD: float = 0.70
    # Multiplicative penalty applied when an extracted value fails its format
    # check. Confidence may only be reduced by validation, never raised.
    FORMAT_MISMATCH_PENALTY: float = 0.60

    # -- translation --------------------------------------------------------
    TRANSLATION_ENABLED: bool = True
    TRANSLATION_PROVIDER: str = "google"

    # ----------------------------------------------------------------------

    @field_validator("ENVIRONMENT")
    @classmethod
    def _valid_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}")
        return v

    def cors_origin_list(self) -> List[str]:
        origins = [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if "*" in origins and self.ENVIRONMENT == "production":
            raise ValueError(
                "CORS_ORIGINS may not contain '*' in production: the API sends credentials."
            )
        return origins

    def ocr_default_languages(self) -> List[str]:
        return [c.strip() for c in self.OCR_LANGUAGES.split(",") if c.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT in ("development", "test")


def _resolve_secret_key(s: Settings) -> str:
    if s.SECRET_KEY:
        return s.SECRET_KEY
    if s.is_production:
        print(
            "FATAL: SECRET_KEY is not set. Refusing to start in production.\n"
            "       Set SECRET_KEY in the environment (see .env.example).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    # Development: a stable machine-local key, generated once, never committed.
    if _DEV_SECRET_FILE.exists():
        return _DEV_SECRET_FILE.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    _DEV_SECRET_FILE.write_text(key, encoding="utf-8")
    print(
        f"[bhumi] No SECRET_KEY set. Generated a development-only key at {_DEV_SECRET_FILE}. "
        "Set SECRET_KEY explicitly before any non-development deployment."
    )
    return key


settings = Settings()
settings.SECRET_KEY = _resolve_secret_key(settings)

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.DEMO_CORPUS_DIR.mkdir(parents=True, exist_ok=True)
