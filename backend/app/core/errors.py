"""
Typed error hierarchy for Bhumi Forensics.

Design rule (BHUMI_FORENSICS_SPEC §2.1): when a processing stage cannot produce a
result, it raises. No stage may substitute invented content for a failure.
"""
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse


class BhumiError(Exception):
    """Base class. Every error carries a stable machine code and a human message."""

    code: str = "BHUMI_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_envelope(self) -> Dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


# --- Processing pipeline ----------------------------------------------------

class ProcessingError(BhumiError):
    """A document processing stage failed. Always surfaced to the officer verbatim."""

    code = "PROCESSING_FAILED"
    http_status = 422
    stage: str = "unknown"


class DocumentRenderError(ProcessingError):
    code = "DOCUMENT_RENDER_FAILED"
    stage = "render"


class ImagePreprocessError(ProcessingError):
    code = "IMAGE_PREPROCESS_FAILED"
    stage = "enhance"


class OcrEngineUnavailableError(ProcessingError):
    """Tesseract (or the configured engine) is not installed or not reachable.

    This is an operations problem, not a document problem. It must never be
    silently converted into 'OCR output'.
    """

    code = "OCR_ENGINE_UNAVAILABLE"
    http_status = 503
    stage = "ocr"


class OcrEmptyResultError(ProcessingError):
    """OCR ran but produced no usable text.

    Legitimate causes: blank page, photograph with no text, unsupported script,
    scan quality too low. The correct response is to tell the officer, not to
    invent a land record.
    """

    code = "OCR_EMPTY_RESULT"
    stage = "ocr"


class NoExtractableFieldsError(ProcessingError):
    """OCR produced text, but nothing in it resembles a land record."""

    code = "NO_LAND_RECORD_FIELDS_FOUND"
    stage = "extract"


class TranslationUnavailableError(BhumiError):
    """Non-fatal: the pipeline continues, original OCR is preserved untranslated."""

    code = "TRANSLATION_UNAVAILABLE"
    http_status = 503


# --- Domain -----------------------------------------------------------------

class ValidationInputError(BhumiError):
    code = "INVALID_INPUT"
    http_status = 400


class InsufficientDataError(BhumiError):
    """A computation was requested that has no data behind it.

    Raised instead of returning a plausible-looking placeholder number.
    """

    code = "INSUFFICIENT_DATA"
    http_status = 409


def register_exception_handlers(app) -> None:
    @app.exception_handler(BhumiError)
    async def _bhumi_error_handler(request: Request, exc: BhumiError):  # noqa: ANN001
        return JSONResponse(status_code=exc.http_status, content=exc.to_envelope())
