import hashlib
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.auth.rbac import (
    CAN_DELETE_DOCUMENTS,
    CAN_READ_DOCUMENTS,
    CAN_UPLOAD,
    require_roles,
)
from app.config import settings
from app.core.errors import DocumentRenderError
from app.models.document import Document, DocumentPage
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.audit_service import audit_service
from app.services.document_service import document_service

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
# Magic bytes, checked against the real file content rather than trusting the
# extension or the client-supplied Content-Type.
MAGIC_PREFIXES = {
    b"%PDF-": ".pdf",
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
    b"II*\x00": ".tiff",
    b"MM\x00*": ".tiff",
}


def _sniff(content: bytes) -> Optional[str]:
    for magic, ext in MAGIC_PREFIXES.items():
        if content.startswith(magic):
            return ext
    return None


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    state: str = Form(...),
    district: str = Form(...),
    tehsil: str = Form(...),
    village: str = Form(...),
    document_type: str = Form("khasra_b1"),
    document_year: int = Form(...),
    language: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_UPLOAD)),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413, detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit."
        )
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    sniffed = _sniff(content)
    if sniffed is None:
        raise HTTPException(
            status_code=400,
            detail="The file content does not match any supported format (PDF, JPEG, PNG, TIFF).",
        )
    if sniffed == ".pdf" and ext != ".pdf":
        raise HTTPException(status_code=400, detail="File content is a PDF but the extension is not .pdf.")

    sha256 = hashlib.sha256(content).hexdigest()
    existing = db.query(Document).filter(Document.sha256 == sha256).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DUPLICATE_UPLOAD",
                "message": "This exact file has already been uploaded.",
                "details": {"existing_document_id": existing.id, "file_name": existing.file_name},
            },
        )

    file_path, file_size, mime_type = document_service.save_upload(content, file.filename)

    doc = Document(
        file_name=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=mime_type,
        sha256=sha256,
        source_class="REAL_UPLOAD",
        state=state,
        district=district,
        tehsil=tehsil,
        village=village,
        document_type=document_type,
        document_year=document_year,
        language=language,
        status="uploaded",
        validation_status="pending",
        uploaded_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        pages = document_service.convert_to_pages(doc.file_path, doc.id)
    except Exception as exc:
        doc.status = "failed"
        doc.processing_error_code = DocumentRenderError.code
        doc.processing_error_message = str(exc)
        doc.processing_failed_stage = "render"
        db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "code": DocumentRenderError.code,
                "message": f"The file was stored but its pages could not be rendered: {exc}",
                "details": {"document_id": doc.id},
            },
        )

    for p in pages:
        db.add(
            DocumentPage(
                document_id=doc.id,
                page_number=p["page_number"],
                original_image_path=p["original_image_path"],
                preprocessed_image_path=p["preprocessed_image_path"],
                width=p["width"],
                height=p["height"],
            )
        )
    doc.page_count = len(pages)
    db.commit()
    db.refresh(doc)

    audit_service.log_event(
        db,
        action="DOCUMENT_UPLOADED",
        user_id=current_user.id,
        document_id=doc.id,
        details={
            "file_name": doc.file_name,
            "sha256": sha256,
            "pages": doc.page_count,
            "location": f"{village}, {tehsil}, {district}, {state}",
        },
    )
    return doc


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    status: Optional[str] = None,
    document_type: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    village: Optional[str] = None,
    source_class: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    query = db.query(Document)
    if status:
        query = query.filter(Document.status == status)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if state:
        query = query.filter(Document.state == state)
    if district:
        query = query.filter(Document.district == district)
    if village:
        query = query.filter(Document.village == village)
    if source_class:
        query = query.filter(Document.source_class == source_class)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (Document.file_name.ilike(s)) | (Document.village.ilike(s)) | (Document.district.ilike(s))
        )
    return (
        query.order_by(Document.created_at.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 500))
        .all()
    )


@router.get("/{id}", response_model=DocumentResponse)
def get_document(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{id}/file")
def get_document_file(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(
            status_code=410,
            detail="The stored original file is no longer present on this server.",
        )
    audit_service.log_event(
        db, action="DOCUMENT_FILE_ACCESSED", user_id=current_user.id, document_id=doc.id, details={}
    )
    return FileResponse(doc.file_path, media_type=doc.mime_type, filename=doc.file_name)


@router.get("/{id}/pages/{page_num}")
def get_page_image(
    id: int,
    page_num: int,
    enhanced: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    page = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == id, DocumentPage.page_number == page_num)
        .first()
    )
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    img_path = page.preprocessed_image_path if enhanced and page.preprocessed_image_path else page.original_image_path
    if not img_path or not os.path.exists(img_path):
        raise HTTPException(
            status_code=410,
            detail="The rendered page image is not present on this server. Re-process the document.",
        )
    return FileResponse(img_path, media_type="image/png")


# Backwards-compatible alias for the previous path shape.
@router.get("/{id}/page/{page_num}", include_in_schema=False)
def get_page_image_legacy(
    id: int,
    page_num: int = 1,
    enhanced: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_DOCUMENTS)),
):
    return get_page_image(id, page_num, enhanced, db, current_user)


@router.delete("/{id}")
def delete_document(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_DELETE_DOCUMENTS)),
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_name = doc.file_name
    db.delete(doc)
    db.commit()
    audit_service.log_event(
        db,
        action="DOCUMENT_DELETED",
        user_id=current_user.id,
        details={"document_id": id, "file_name": file_name},
    )
    return {"message": "Document deleted", "document_id": id}
