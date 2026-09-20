from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class LandRecordBase(BaseModel):
    state: str
    district: str
    tehsil: str
    village: str
    owner_name: str
    father_name: Optional[str] = None
    address: Optional[str] = None
    ownership_type: Optional[str] = "Individual"
    survey_number: Optional[str] = None
    khasra_number: str
    khata_number: str
    plot_number: Optional[str] = None
    area: float
    area_unit: Optional[str] = "hectare"
    land_classification: Optional[str] = "Agricultural"
    mutation_number: Optional[str] = None
    mutation_date: Optional[date] = None
    mutation_type: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[date] = None
    registration_office: Optional[str] = None

class LandRecordCreate(LandRecordBase):
    document_id: Optional[int] = None
    metadata_json: Optional[Dict[str, Any]] = None

class LandRecordUpdate(BaseModel):
    owner_name: Optional[str] = None
    father_name: Optional[str] = None
    khasra_number: Optional[str] = None
    khata_number: Optional[str] = None
    area: Optional[float] = None
    area_unit: Optional[str] = None
    land_classification: Optional[str] = None
    village: Optional[str] = None
    tehsil: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    verification_status: Optional[str] = None
    verification_notes: Optional[str] = None

class LandRecordResponse(LandRecordBase):
    id: int
    document_id: Optional[int] = None
    verification_status: str
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ViewerLandRecordResponse(BaseModel):
    """Public-safe view of a LandRecord for the citizen/viewer role.

    Deliberately excludes everything internal: `verified_by` (a staff user
    ID), `verification_notes` (an officer's internal remarks), `document_id`
    and `metadata_json` (internal linkage/processing metadata), and the
    create/update timestamps. Field selection filtered at this schema level,
    not by hiding columns in the UI -- the API itself never sends them to a
    viewer.
    """
    id: int
    state: str
    district: str
    tehsil: str
    village: str
    owner_name: str
    father_name: Optional[str] = None
    ownership_type: Optional[str] = "Individual"
    survey_number: Optional[str] = None
    khasra_number: str
    khata_number: str
    plot_number: Optional[str] = None
    area: float
    area_unit: Optional[str] = "hectare"
    land_classification: Optional[str] = "Agricultural"
    mutation_number: Optional[str] = None
    mutation_date: Optional[date] = None
    mutation_type: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[date] = None
    registration_office: Optional[str] = None
    verification_status: str

    class Config:
        from_attributes = True

class VerificationSubmission(BaseModel):
    action: str  # approved, edited_approved, rejected, reprocessing_requested
    notes: Optional[str] = ""
    corrected_fields: Optional[Dict[str, Any]] = None  # {field_name: new_value}
