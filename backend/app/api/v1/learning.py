from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_READ_LEARNING, require_roles
from app.models.user import User
from app.models.training import TrainingCorrection
from app.utils.terminology import TERMINOLOGY_DICTIONARY, STATE_TERMINOLOGY_OVERLAYS

router = APIRouter(prefix="/learning", tags=["Active Learning & Terminology"])

@router.get("/corrections")
def get_training_corrections(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_LEARNING)),
):
    corrections = db.query(TrainingCorrection).order_by(TrainingCorrection.created_at.desc()).limit(50).all()
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "field_name": c.field_name,
            "original_value": c.original_value,
            "corrected_value": c.corrected_value,
            "document_type": c.document_type,
            "language": c.language,
            "notes": c.notes,
            "created_at": c.created_at
        }
        for c in corrections
    ]

@router.get("/terminology")
def get_terminology_dictionary(current_user: User = Depends(require_roles(CAN_READ_LEARNING))):
    return {
        "dictionary": TERMINOLOGY_DICTIONARY,
        "state_overlays": STATE_TERMINOLOGY_OVERLAYS
    }
