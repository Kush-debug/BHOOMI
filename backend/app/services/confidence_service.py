"""
Document-level confidence aggregation over extracted fields.

Only fields that carry a measured confidence contribute. Fields with confidence
None (not computable) and fields sourced from the upload form rather than the
document are excluded and reported separately, instead of being silently
defaulted to a plausible number.
"""
from typing import Any, Dict, List, Optional

from app.config import settings

FIELD_WEIGHTS = {
    "khasra_number": 2.0,
    "khata_number": 2.0,
    "survey_number": 2.0,
    "owner_name": 2.0,
    "area": 2.0,
    "village": 1.5,
    "father_name": 1.0,
    "tehsil": 1.0,
    "district": 1.0,
    "mutation_number": 0.8,
    "registration_number": 0.8,
}


class ConfidenceService:
    def calculate_document_confidence(self, extracted_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        scored = [
            f
            for f in extracted_fields
            if f.get("confidence") is not None and f.get("provenance", "DOCUMENT_OCR") == "DOCUMENT_OCR"
        ]
        unscored = [f for f in extracted_fields if f.get("confidence") is None]

        if not scored:
            return {
                "overall_confidence": None,
                "basis": "no field carried a measurable confidence",
                "scored_field_count": 0,
                "unscored_field_count": len(unscored),
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "requires_human_verification": True,
                "uncertain_fields": [
                    {"field": f.get("standardized_field"), "confidence": None, "band": "unknown"}
                    for f in unscored
                ],
            }

        total_weighted = 0.0
        total_weight = 0.0
        high = medium = low = 0
        uncertain: List[Dict[str, Any]] = []

        for field in scored:
            name = field.get("standardized_field", "")
            conf = float(field["confidence"])
            weight = FIELD_WEIGHTS.get(name, 1.0)
            total_weighted += conf * weight
            total_weight += weight

            if conf >= settings.CONFIDENCE_HIGH_THRESHOLD:
                high += 1
            elif conf >= settings.CONFIDENCE_MEDIUM_THRESHOLD:
                medium += 1
                uncertain.append({"field": name, "confidence": conf, "band": "medium"})
            else:
                low += 1
                uncertain.append({"field": name, "confidence": conf, "band": "low"})

        for field in unscored:
            uncertain.append(
                {"field": field.get("standardized_field"), "confidence": None, "band": "unknown"}
            )

        overall: Optional[float] = round(total_weighted / total_weight, 4) if total_weight else None

        return {
            "overall_confidence": overall,
            "basis": "weighted mean of per-field OCR-derived confidences",
            "scored_field_count": len(scored),
            "unscored_field_count": len(unscored),
            "high_count": high,
            "medium_count": medium,
            "low_count": low,
            "requires_human_verification": bool(
                low or unscored or (overall is not None and overall < settings.CONFIDENCE_HIGH_THRESHOLD)
            ),
            "uncertain_fields": uncertain,
        }


confidence_service = ConfidenceService()
