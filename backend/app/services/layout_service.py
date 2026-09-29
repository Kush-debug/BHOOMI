from typing import List, Dict, Any
from app.utils.opencv_utils import detect_table_grid_and_stamps

class LayoutService:
    def analyze_document_layout(self, image_path: str, ocr_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Combines OpenCV visual contours with OCR text positions to classify document regions:
        - Table Grid
        - Header & Metadata
        - Field Value Pairs
        - Official Stamps / Seals
        - Handwritten Annotations
        """
        cv_regions = detect_table_grid_and_stamps(image_path)
        combined_regions = list(cv_regions)

        for block in ocr_blocks:
            b_type = block.get("type", "text_block")
            if b_type.startswith("field_"):
                combined_regions.append({
                    "type": "field_region",
                    "subtype": b_type,
                    "bbox": block.get("bbox", [0, 0, 100, 30]),
                    "text": block.get("text", ""),
                    "confidence": block.get("confidence", 0.95)
                })

        return combined_regions

layout_service = LayoutService()
