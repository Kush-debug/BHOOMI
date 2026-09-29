import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.evidence import router as evidence_router
from app.api.v1.findings import router as findings_router
from app.api.v1.gis import router as gis_router
from app.api.v1.investigation_cases import router as investigation_cases_router
from app.api.v1.learning import router as learning_router
from app.api.v1.locations import router as locations_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.parcels import router as parcels_router
from app.api.v1.processing import router as processing_router
from app.api.v1.records import router as records_router
from app.api.v1.validation import router as validation_router
from app.api.v1.verification import router as verification_router
from app.config import settings
from app.core.errors import register_exception_handlers
from app.database.seed_data import seed_reference_data
from app.database.session import SessionLocal
from app.services.ocr_service import ocr_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s | %(message)s",
)
logger = logging.getLogger("bhumi")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Evidence-backed land record intelligence. AI proposes, evidence explains, "
        "the authorised officer decides."
    ),
    version="2.0.0-phase6",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Schema is owned by Alembic. `Base.metadata.create_all()` was removed so the
# running schema and the migration history can never diverge.
# Run `alembic upgrade head` before starting the API.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

register_exception_handlers(app)

for router in (
    auth_router,
    admin_router,
    locations_router,
    documents_router,
    processing_router,
    evidence_router,
    parcels_router,
    findings_router,
    investigation_cases_router,
    verification_router,
    records_router,
    gis_router,
    validation_router,
    audit_router,
    learning_router,
    notifications_router,
    dashboard_router,
    analytics_router,
):
    app.include_router(router, prefix=settings.API_V1_STR)


@app.on_event("startup")
def on_startup() -> None:
    db = SessionLocal()
    try:
        seed_reference_data(db)
    finally:
        db.close()

    status = ocr_service.engine_status()
    if not status["available"]:
        logger.warning(
            "OCR engine '%s' is NOT available. Document processing will fail with a clear "
            "error until tesseract is installed. It will not fall back to generated text.",
            status["engine"],
        )
    else:
        logger.info(
            "OCR engine %s %s ready. Language packs installed: %s",
            status["engine"],
            status["version"],
            ", ".join(status["installed_language_packs"]) or "none",
        )


@app.get("/")
def root():
    return {
        "system": settings.PROJECT_NAME,
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "api_v1": settings.API_V1_STR,
        "docs": "/docs" if not settings.is_production else None,
    }


@app.get("/health")
def health():
    """Liveness plus an honest report of what the OCR stack can actually do."""
    return {"status": "healthy", "ocr": ocr_service.engine_status()}
