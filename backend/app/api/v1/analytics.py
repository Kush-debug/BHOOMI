"""
Analytics computed from stored rows.

Replaces the hardcoded charts in the old Reports page, which claimed measured OCR
accuracy figures ("Hindi 96.2% across 18,450 documents") for evaluations that had
never been run (ARCHITECTURE_AUDIT §4.4).

Note the vocabulary: these endpoints report *confidence*, which the OCR engine
reports about its own output. They do not report *accuracy*, which would require
a labelled ground-truth set. The distinction is preserved in the field names so
the UI cannot accidentally mislabel it.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import CAN_READ_ANALYTICS, require_roles
from app.models.document import Document
from app.models.ocr import Claim
from app.models.training import TrainingCorrection
from app.models.user import User
from app.models.validation import ValidationResult

router = APIRouter(prefix="/analytics", tags=["Analytics"])

REAL = "REAL_UPLOAD"


@router.get("/quality")
def quality_metrics(
    include_demo: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_ANALYTICS)),
) -> Dict[str, Any]:
    """Mean OCR confidence by detected language and by document type."""

    def scoped(q):
        return q if include_demo else q.filter(Document.source_class == REAL)

    by_language = [
        {
            "language": row[0] or "unknown",
            "documents": int(row[1] or 0),
            "mean_ocr_confidence": round(float(row[2]) * 100, 1) if row[2] is not None else None,
        }
        for row in scoped(
            db.query(
                Document.detected_language_name,
                func.count(Document.id),
                func.avg(Document.ocr_confidence),
            ).filter(Document.ocr_confidence.isnot(None))
        )
        .group_by(Document.detected_language_name)
        .all()
    ]

    by_type = [
        {
            "document_type": row[0] or "unknown",
            "documents": int(row[1] or 0),
            "mean_extraction_confidence": round(float(row[2]) * 100, 1) if row[2] is not None else None,
        }
        for row in scoped(
            db.query(
                Document.document_type,
                func.count(Document.id),
                func.avg(Document.extraction_confidence),
            ).filter(Document.extraction_confidence.isnot(None))
        )
        .group_by(Document.document_type)
        .all()
    ]

    # Evidence grounding: how many extracted values could be tied back to real
    # OCR word geometry. This is the honest replacement for a fake accuracy chart.
    # Only the current (ACCEPTED) claims count — a superseded claim from an
    # earlier OCR run or a prior officer edit isn't part of today's picture.
    grounded = int(
        db.query(func.count(Claim.id))
        .filter(Claim.lifecycle_status == "ACCEPTED", Claim.bbox_source == "OCR_WORD_BOX")
        .scalar()
        or 0
    )
    ungrounded = int(
        db.query(func.count(Claim.id))
        .filter(Claim.lifecycle_status == "ACCEPTED", Claim.bbox_source != "OCR_WORD_BOX")
        .scalar()
        or 0
    )

    return {
        "measurement_note": (
            "These are engine-reported confidence values, not accuracy. Accuracy requires "
            "evaluation against a labelled ground-truth set, which has not been run."
        ),
        "documents_measured": sum(x["documents"] for x in by_language),
        "by_language": by_language,
        "by_document_type": by_type,
        "evidence_grounding": {
            "fields_with_source_region": grounded,
            "fields_without_source_region": ungrounded,
            "grounded_share_pct": (
                round(grounded / (grounded + ungrounded) * 100, 1) if (grounded + ungrounded) else None
            ),
        },
    }


@router.get("/throughput")
def throughput_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_ANALYTICS)),
) -> Dict[str, Any]:
    """Pipeline outcomes and human workload, counted from rows."""
    status_counts = {
        row[0]: int(row[1])
        for row in db.query(Document.status, func.count(Document.id))
        .filter(Document.source_class == REAL)
        .group_by(Document.status)
        .all()
    }

    failures = [
        {"code": row[0], "stage": row[1], "count": int(row[2])}
        for row in db.query(
            Document.processing_error_code,
            Document.processing_failed_stage,
            func.count(Document.id),
        )
        .filter(Document.processing_error_code.isnot(None))
        .group_by(Document.processing_error_code, Document.processing_failed_stage)
        .all()
    ]

    findings_by_rule = [
        {"rule": row[0], "severity": row[1], "count": int(row[2])}
        for row in db.query(
            ValidationResult.rule_name, ValidationResult.severity, func.count(ValidationResult.id)
        )
        .group_by(ValidationResult.rule_name, ValidationResult.severity)
        .all()
    ]

    corrections_by_field = [
        {"field": row[0], "corrections": int(row[1])}
        for row in db.query(TrainingCorrection.field_name, func.count(TrainingCorrection.id))
        .group_by(TrainingCorrection.field_name)
        .order_by(func.count(TrainingCorrection.id).desc())
        .all()
    ]

    return {
        "status_counts": status_counts,
        "processing_failures": failures,
        "findings_by_rule": findings_by_rule,
        "human_corrections_by_field": corrections_by_field,
        "total_human_corrections": int(db.query(func.count(TrainingCorrection.id)).scalar() or 0),
    }
