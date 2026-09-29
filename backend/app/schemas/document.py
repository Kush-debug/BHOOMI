from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class DocumentPageResponse(BaseModel):
    id: int
    page_number: int
    original_image_path: str
    preprocessed_image_path: Optional[str] = None
    width: int
    height: int

    class Config:
        from_attributes = True


class ExtractedFieldResponse(BaseModel):
    id: int
    field_name: str
    standardized_field: str
    field_value: Optional[str] = None
    original_value: Optional[str] = None
    translated_value: Optional[str] = None
    transliteration: Optional[str] = None
    translations_json: Optional[Dict[str, str]] = {}

    # None means "not computable", never a filler number. The UI must render
    # this as "confidence unknown" rather than as a score.
    confidence: Optional[float] = None
    confidence_basis: Optional[str] = None
    confidence_breakdown: Optional[Dict[str, Any]] = {}

    source_text: Optional[str] = None
    page_number: Optional[int] = None

    # None when OCR provided no geometry for this value.
    bounding_box: Optional[Dict[str, Any]] = None
    bbox_source: str = "NONE"          # OCR_WORD_BOX | OCR_LINE_BOX | MANUAL | NONE
    provenance: str = "DOCUMENT_OCR"   # DOCUMENT_OCR | UPLOAD_METADATA | OFFICER_CORRECTION
    status: str

    # Phase 2 (evidence foundation): this value is backed by a Claim row.
    # `evidence_region_id` set means /claims/{id}/evidence can show the exact
    # OCR region; `lifecycle_status` distinguishes the current value from a
    # superseded one when a caller asks to see history.
    evidence_region_id: Optional[int] = None
    lifecycle_status: str = "ACCEPTED"  # ACCEPTED | SUPERSEDED | REJECTED
    asserted_by: str = "SYSTEM"         # SYSTEM | OFFICER

    class Config:
        from_attributes = True


class OCRResultResponse(BaseModel):
    id: int
    page_number: int
    raw_text: str
    layout_blocks: List[Dict[str, Any]] = []
    detected_language: Optional[str] = None
    average_confidence: Optional[float] = None
    engine_used: str
    engine_version: Optional[str] = None
    engine_languages: Optional[str] = None
    word_count: Optional[int] = 0
    page_width: Optional[int] = None
    page_height: Optional[int] = None

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    document_uuid: str
    file_name: str
    file_size: int
    mime_type: str
    sha256: Optional[str] = None
    page_count: Optional[int] = None
    source_class: str = "REAL_UPLOAD"

    state: str
    district: str
    tehsil: str
    village: str
    document_type: str
    document_year: int
    language: str

    detected_language: Optional[str] = None
    detected_language_name: Optional[str] = None
    target_language: Optional[str] = None

    language_confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None
    translation_confidence: Optional[float] = None
    validation_confidence: Optional[float] = None

    original_ocr_text: Optional[str] = None
    translated_text: Optional[str] = None

    status: str
    validation_status: str
    processing_error_code: Optional[str] = None
    processing_error_message: Optional[str] = None
    processing_failed_stage: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    pages: List[DocumentPageResponse] = []
    extracted_fields: List[ExtractedFieldResponse] = []

    class Config:
        from_attributes = True
