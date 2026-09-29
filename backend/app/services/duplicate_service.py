from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.record import LandRecord

class DuplicateService:
    def check_duplicate(self, db: Session, candidate: Dict[str, Any], exclude_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Detects potential duplicate land records across:
        - Exact Khasra + Khata + Village + District match
        - Same Khasra + Village with similar Owner Name
        Returns list of matching duplicates with similarity score.
        """
        khasra = candidate.get("khasra_number", "").strip()
        khata = candidate.get("khata_number", "").strip()
        village = candidate.get("village", "").strip()
        district = candidate.get("district", "").strip()
        owner = candidate.get("owner_name", "").strip().lower()

        query = db.query(LandRecord).filter(
            LandRecord.village == village,
            LandRecord.district == district
        )
        if exclude_id:
            query = query.filter(LandRecord.id != exclude_id)

        candidates = query.all()
        duplicates = []

        for rec in candidates:
            score = 0
            reasons = []

            if rec.khasra_number == khasra:
                score += 45
                reasons.append(f"Exact Khasra Number match ({khasra})")
            
            if rec.khata_number == khata:
                score += 25
                reasons.append(f"Exact Khata Number match ({khata})")

            rec_owner = rec.owner_name.strip().lower()
            if rec_owner == owner:
                score += 30
                reasons.append(f"Identical Owner Name ({rec.owner_name})")
            elif any(part in rec_owner for part in owner.split()) or any(part in owner for part in rec_owner.split()):
                score += 15
                reasons.append(f"Partial Owner Name overlap ({rec.owner_name})")

            if score >= 60:
                duplicates.append({
                    "record_id": rec.id,
                    "khasra_number": rec.khasra_number,
                    "khata_number": rec.khata_number,
                    "owner_name": rec.owner_name,
                    "area": rec.area,
                    "similarity_score": min(score, 100),
                    "reasons": reasons,
                    "status": "Possible Duplicate"
                })

        return duplicates

duplicate_service = DuplicateService()
