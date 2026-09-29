import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.validation import ValidationResult, MasterLocation, MasterLandRegistry
from app.models.document import Document
from app.services.duplicate_service import duplicate_service

class ValidationService:
    # Rules attempted for every document. Used to turn the anomaly count into a
    # real pass-rate instead of the 0.96 literal the pipeline used to assign.
    RULES_EXECUTED_PER_DOCUMENT = 6

    def validate_extracted_data(
        self, 
        db: Session, 
        doc: Document, 
        fields_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Executes multi-tier validation:
        1. Rule-Based Validation (Formats, positive area, non-empty identifiers)
        2. Location Hierarchy Consistency (Village -> Tehsil -> District -> State)
        3. Cross-Database Validation against Authoritative Master Land Registry
        4. Duplicate Detection (Khasra + Khata + Owner overlap)
        """
        anomalies = []

        # --- Tier 1: Rule-Based Validation ---
        # 1.1 Non-zero & Positive Area Check
        area_val = fields_dict.get("area")
        try:
            area_float = float(area_val) if area_val is not None else 0.0
            if area_float <= 0:
                anomalies.append({
                    "validation_type": "rule_based",
                    "rule_name": "RULE_AREA_POSITIVE",
                    "severity": "error",
                    "field_name": "area",
                    "expected_value": "> 0.00",
                    "actual_value": str(area_val),
                    "message": "Land area must be strictly greater than zero."
                })
        except (ValueError, TypeError):
            anomalies.append({
                "validation_type": "rule_based",
                "rule_name": "RULE_AREA_NUMERIC",
                "severity": "error",
                "field_name": "area",
                "expected_value": "Numeric value (e.g. 0.75)",
                "actual_value": str(area_val),
                "message": f"Invalid land area format: '{area_val}' is not a valid number."
            })

        # 1.2 Mandatory Land Identifiers
        if not fields_dict.get("khasra_number"):
            anomalies.append({
                "validation_type": "rule_based",
                "rule_name": "RULE_REQUIRED_KHASRA",
                "severity": "error",
                "field_name": "khasra_number",
                "expected_value": "Non-empty Khasra / Gata No.",
                "actual_value": "None",
                "message": "Khasra / Gata Number is mandatory for land record registration."
            })

        if not fields_dict.get("owner_name"):
            anomalies.append({
                "validation_type": "rule_based",
                "rule_name": "RULE_REQUIRED_OWNER",
                "severity": "error",
                "field_name": "owner_name",
                "expected_value": "Non-empty Owner Name",
                "actual_value": "None",
                "message": "Landholder / Owner name is mandatory."
            })

        # --- Tier 2: Location Hierarchy Validation ---
        state = fields_dict.get("state", doc.state)
        district = fields_dict.get("district", doc.district)
        tehsil = fields_dict.get("tehsil", doc.tehsil)
        village = fields_dict.get("village", doc.village)

        loc_match = db.query(MasterLocation).filter(
            MasterLocation.state == state,
            MasterLocation.district == district,
            MasterLocation.tehsil == tehsil,
            MasterLocation.village == village
        ).first()

        if not loc_match:
            # Look for the same village under a DIFFERENT tehsil or district.
            # The previous implementation matched on village name alone, so it
            # could report that a village belongs to the very tehsil it was filed
            # under (ARCHITECTURE_AUDIT §4.9).
            other_tehsil = db.query(MasterLocation).filter(
                MasterLocation.village == village,
                (MasterLocation.tehsil != tehsil) | (MasterLocation.district != district),
            ).first()
            if other_tehsil:
                anomalies.append({
                    "validation_type": "hierarchy_check",
                    "rule_name": "RULE_LOCATION_HIERARCHY_MISMATCH",
                    "severity": "error",
                    "field_name": "village",
                    "expected_value": f"Tehsil: {other_tehsil.tehsil}, District: {other_tehsil.district}",
                    "actual_value": f"Tehsil: {tehsil}, District: {district}",
                    "message": f"Location hierarchy mismatch: Village '{village}' belongs to Tehsil '{other_tehsil.tehsil}', not '{tehsil}'."
                })
            else:
                anomalies.append({
                    "validation_type": "hierarchy_check",
                    "rule_name": "RULE_LOCATION_UNVERIFIED",
                    "severity": "warning",
                    "field_name": "village",
                    "expected_value": "Recognized Village in Master Directory",
                    "actual_value": f"{village}, {tehsil}, {district}",
                    "message": f"Village '{village}' not found in official Revenue Master directory."
                })

        # --- Tier 3: Cross-Database Validation against Master Land Registry ---
        khasra = fields_dict.get("khasra_number")
        if khasra:
            master_rec = db.query(MasterLandRegistry).filter(
                MasterLandRegistry.khasra_number == khasra,
                MasterLandRegistry.village == village,
                MasterLandRegistry.district == district
            ).first()

            if master_rec:
                # 3.1 Check Area Match
                try:
                    ext_area = float(fields_dict.get("area", 0.0))
                    if abs(master_rec.area - ext_area) > 0.01:
                        anomalies.append({
                            "validation_type": "cross_database",
                            "rule_name": "RULE_CROSS_DB_AREA_MISMATCH",
                            "severity": "error",
                            "field_name": "area",
                            "expected_value": f"{master_rec.area} {master_rec.area_unit}",
                            "actual_value": f"{ext_area} {fields_dict.get('area_unit', 'hectare')}",
                            "message": f"Area mismatch detected: Master Registry has {master_rec.area} {master_rec.area_unit}, but extracted document shows {ext_area} {fields_dict.get('area_unit', 'hectare')}."
                        })
                except (ValueError, TypeError):
                    pass

                # 3.2 Check Owner Name Match
                ext_owner = fields_dict.get("owner_name", "").strip()
                if ext_owner and master_rec.owner_name.strip() != ext_owner:
                    anomalies.append({
                        "validation_type": "cross_database",
                        "rule_name": "RULE_CROSS_DB_OWNER_MISMATCH",
                        "severity": "warning",
                        "field_name": "owner_name",
                        "expected_value": master_rec.owner_name,
                        "actual_value": ext_owner,
                        "message": f"Owner name discrepancy: Master Registry has '{master_rec.owner_name}', extracted has '{ext_owner}'."
                    })

        # --- Tier 4: Duplicate Record Detection ---
        candidate_data = {
            "khasra_number": fields_dict.get("khasra_number", ""),
            "khata_number": fields_dict.get("khata_number", ""),
            "village": village,
            "district": district,
            "owner_name": fields_dict.get("owner_name", "")
        }
        duplicates = duplicate_service.check_duplicate(db, candidate_data)
        for dup in duplicates:
            anomalies.append({
                "validation_type": "duplicate_check",
                "rule_name": "RULE_POSSIBLE_DUPLICATE",
                "severity": "warning",
                "field_name": "khasra_number",
                "expected_value": "Unique Record",
                "actual_value": f"Match with Record #{dup['record_id']} ({dup['owner_name']})",
                "message": f"Possible duplicate record detected ({dup['similarity_score']}% match): {', '.join(dup['reasons'])}. Sent for human verification."
            })

        return anomalies

validation_service = ValidationService()
