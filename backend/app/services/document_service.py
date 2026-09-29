import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.config import settings
from app.utils.opencv_utils import normalize_raw_image, preprocess_image_for_ocr

class DocumentService:
    def save_upload(self, file_bytes: bytes, original_filename: str) -> Tuple[str, int, str]:
        """Saves uploaded document into permanent storage."""
        ext = Path(original_filename).suffix.lower()
        if not ext:
            ext = ".pdf"
        # Never build a path from an untrusted filename.
        stem = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(original_filename or "document").name)[:80]
        safe_name = f"doc_{uuid.uuid4().hex[:12]}_{stem}"
        dest_path = settings.UPLOAD_DIR / safe_name
        
        with open(dest_path, "wb") as f:
            f.write(file_bytes)
        
        file_size = len(file_bytes)
        mime_type = "application/pdf" if ext == ".pdf" else f"image/{ext.replace('.', '')}"
        return str(dest_path), file_size, mime_type

    def convert_to_pages(self, doc_path: str, doc_id: int) -> List[Dict[str, Any]]:
        """
        Converts PDF or Image into page images, performs OpenCV preprocessing,
        and saves both raw and enhanced image files.
        """
        pages_info = []
        path_obj = Path(doc_path)
        ext = path_obj.suffix.lower()

        page_dir = settings.UPLOAD_DIR / f"doc_{doc_id}_pages"
        page_dir.mkdir(parents=True, exist_ok=True)

        if ext == ".pdf":
            # Render the ACTUAL uploaded PDF pages at high resolution.
            # The old implementation created a synthetic land-record canvas,
            # which is why uploaded PDFs were not really being OCR'd.
            try:
                import fitz  # PyMuPDF

                pdf = fitz.open(doc_path)
                if pdf.page_count == 0:
                    raise ValueError("PDF contains no pages")

                for page_index in range(pdf.page_count):
                    page_num = page_index + 1
                    raw_page_path = page_dir / f"page_{page_num}_raw.png"
                    preproc_page_path = page_dir / f"page_{page_num}_enhanced.png"

                    page = pdf.load_page(page_index)
                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(2.5, 2.5),
                        alpha=False
                    )
                    pix.save(str(raw_page_path))

                    cv_res = preprocess_image_for_ocr(
                        str(raw_page_path),
                        str(preproc_page_path)
                    )

                    pages_info.append({
                        "page_number": page_num,
                        "original_image_path": str(raw_page_path),
                        "preprocessed_image_path": str(preproc_page_path),
                        "width": cv_res["width"],
                        "height": cv_res["height"]
                    })

                pdf.close()

            except Exception as exc:
                raise RuntimeError(f"Could not render uploaded PDF: {exc}") from exc
        else:
            # Single image file (JPG, PNG, TIFF)
            raw_page_path = page_dir / "page_1_raw.png"
            preproc_page_path = page_dir / "page_1_enhanced.png"

            # Upscales small phone photos before anything else touches the
            # file, so the raw and enhanced images stay pixel-aligned (see
            # normalize_raw_image's docstring).
            normalize_raw_image(str(doc_path), str(raw_page_path))
            cv_res = preprocess_image_for_ocr(str(raw_page_path), str(preproc_page_path))

            pages_info.append({
                "page_number": 1,
                "original_image_path": str(raw_page_path),
                "preprocessed_image_path": str(preproc_page_path),
                "width": cv_res["width"],
                "height": cv_res["height"]
            })

        return pages_info

document_service = DocumentService()
