from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models.training import TrainingCorrection

class LearningService:
    def record_correction(
        self,
        db: Session,
        document_id: int,
        field_name: str,
        original_val: Optional[str],
        corrected_val: str,
        verifier_id: Optional[int] = None,
        doc_type: str = "khasra_b1",
        language: str = "hi",
        bounding_box: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> TrainingCorrection:
        """Stores human-in-the-loop correction for active learning & future fine-tuning."""
        tc = TrainingCorrection(
            document_id=document_id,
            field_name=field_name,
            original_value=original_val,
            corrected_value=corrected_val,
            verifier_id=verifier_id,
            document_type=doc_type,
            language=language,
            bounding_box=bounding_box or {},
            notes=notes
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        return tc

    def get_corrections(self, db: Session, limit: int = 100) -> List[Dict[str, Any]]:
        corrections = db.query(TrainingCorrection).order_by(TrainingCorrection.created_at.desc()).limit(limit).all()
        return [
            {
                "id": c.id,
                "document_id": c.document_id,
                "field_name": c.field_name,
                "original_value": c.original_value,
                "corrected_value": c.corrected_value,
                "document_type": c.document_type,
                "language": c.language,
                "bounding_box": c.bounding_box,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in corrections
        ]

learning_service = LearningService()
