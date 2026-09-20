"""
Operational dashboard metrics.

Every number here is a query result. The previous implementation returned
`total_documents: 25430`, a seven-day `processing_timeline` and a
`confidence_distribution` that were hardcoded literals (ARCHITECTURE_AUDIT §4.4).
Empty deployments now return zeros and empty arrays, and the UI renders an empty
state rather than invented activity.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import ALL_ROLES, CAN_READ_ANALYTICS, require_roles
from app.models.document import Document
from app.models.gis import GISParcel
from app.models.record import LandRecord
from app.models.user import User
from app.models.validation import ValidationResult
from app.services.ocr_service import ocr_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

REAL = "REAL_UPLOAD"


@router.get("/public-summary")
def get_public_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(ALL_ROLES)),
) -> Dict[str, Any]:
    """Safe, citizen-facing counts for the Viewer dashboard.

    Deliberately separate from /stats: that endpoint is staff-only and mixes
    in OCR/processing-pipeline metrics that are not meant for public view.
    Everything here is a real count -- no placeholder or invented number.
    """
    return {
        "verified_land_records": int(
            db.query(func.count(LandRecord.id))
            .filter(LandRecord.verification_status == "verified")
            .scalar()
            or 0
        ),
        "verified_gis_parcels": int(
            db.query(func.count(GISParcel.id))
            .filter(GISParcel.verification_status == "verified")
            .scalar()
            or 0
        ),
    }


@router.get("/stats")
def get_dashboard_stats(
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_ANALYTICS)),
) -> Dict[str, Any]:
    """Counts computed from the database.

    By default only REAL_UPLOAD documents are counted. Synthetic seed data is
    reported separately so it can never inflate an operational metric.
    """
    base = db.query(Document)
    if not include_demo:
        base = base.filter(Document.source_class == REAL)

    def count(*criteria) -> int:
        q = db.query(func.count(Document.id))
        if not include_demo:
            q = q.filter(Document.source_class == REAL)
        for c in criteria:
            q = q.filter(c)
        return int(q.scalar() or 0)

    total = count()
    uploaded = count(Document.status == "uploaded")
    processing = count(Document.status == "processing")
    pending_verification = count(Document.status == "verification_pending")
    verified = count(Document.status == "verified")
    rejected = count(Document.status == "rejected")
    failed = count(Document.status == "failed")
    processed = count(Document.status.in_(["processed", "verification_pending", "verified"]))

    demo_documents = int(
        db.query(func.count(Document.id)).filter(Document.source_class != REAL).scalar() or 0
    )

    open_findings = int(
        db.query(func.count(ValidationResult.id)).filter(ValidationResult.status == "failed").scalar() or 0
    )

    avg_ocr = db.query(func.avg(Document.ocr_confidence)).filter(Document.ocr_confidence.isnot(None))
    avg_ext = db.query(func.avg(Document.extraction_confidence)).filter(
        Document.extraction_confidence.isnot(None)
    )
    if not include_demo:
        avg_ocr = avg_ocr.filter(Document.source_class == REAL)
        avg_ext = avg_ext.filter(Document.source_class == REAL)
    avg_ocr_val = avg_ocr.scalar()
    avg_ext_val = avg_ext.scalar()

    # Status distribution — real counts only, no colour-coded filler entries.
    status_distribution = [
        {"name": "Verified", "value": verified},
        {"name": "Pending verification", "value": pending_verification},
        {"name": "Processing", "value": processing},
        {"name": "Awaiting processing", "value": uploaded},
        {"name": "Failed", "value": failed},
        {"name": "Rejected", "value": rejected},
    ]

    # Confidence bands, computed from stored per-document OCR confidence.
    bands = [("90-100%", 0.90, 1.01), ("80-89%", 0.80, 0.90), ("70-79%", 0.70, 0.80), ("< 70%", 0.0, 0.70)]
    confidence_distribution: List[Dict[str, Any]] = []
    for label, lo, hi in bands:
        q = db.query(func.count(Document.id)).filter(
            Document.ocr_confidence.isnot(None),
            Document.ocr_confidence >= lo,
            Document.ocr_confidence < hi,
        )
        if not include_demo:
            q = q.filter(Document.source_class == REAL)
        confidence_distribution.append({"range": label, "count": int(q.scalar() or 0)})
    unmeasured = count(Document.ocr_confidence.is_(None))
    confidence_distribution.append({"range": "not measured", "count": unmeasured})

    # Last 7 days of real activity.
    today = datetime.utcnow().date()
    timeline: List[Dict[str, Any]] = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        q = db.query(
            func.count(Document.id),
            func.sum(case((Document.status == "verified", 1), else_=0)),
        ).filter(Document.created_at >= start, Document.created_at < end)
        if not include_demo:
            q = q.filter(Document.source_class == REAL)
        row = q.one()
        timeline.append(
            {"date": day.isoformat(), "uploaded": int(row[0] or 0), "verified": int(row[1] or 0)}
        )

    # Geography breakdowns from real rows only.
    def by(column):
        q = db.query(
            column,
            func.count(Document.id),
            func.sum(case((Document.status == "verified", 1), else_=0)),
        )
        if not include_demo:
            q = q.filter(Document.source_class == REAL)
        return q.group_by(column).all()

    state_progress = [
        {
            "state": r[0],
            "total": int(r[1] or 0),
            "verified": int(r[2] or 0),
            "rate": round((float(r[2] or 0) / r[1]) * 100, 1) if r[1] else 0.0,
        }
        for r in by(Document.state)
        if r[0]
    ]
    district_progress = [
        {"district": r[0], "total": int(r[1] or 0), "verified": int(r[2] or 0)}
        for r in by(Document.district)
        if r[0]
    ]

    return {
        "scope": "real_uploads_only" if not include_demo else "all_documents",
        "total_documents": total,
        "processed_documents": processed,
        "verified_documents": verified,
        "pending_verification": pending_verification,
        "failed_documents": failed,
        "rejected_documents": rejected,
        "open_findings": open_findings,
        "verified_land_records": int(
            db.query(func.count(LandRecord.id)).filter(LandRecord.verification_status == "verified").scalar() or 0
        ),
        # None means "not measured yet", not zero and not a plausible placeholder.
        "average_ocr_confidence": round(float(avg_ocr_val) * 100, 1) if avg_ocr_val is not None else None,
        "average_extraction_confidence": round(float(avg_ext_val) * 100, 1) if avg_ext_val is not None else None,
        "demo_documents_excluded": demo_documents,
        "status_distribution": status_distribution,
        "confidence_distribution": confidence_distribution,
        "processing_timeline": timeline,
        "state_progress": state_progress,
        "district_progress": district_progress,
        "ocr_engine": ocr_service.engine_status(),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
