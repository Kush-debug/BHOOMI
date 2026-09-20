"""
Cadastral map sheet vectorisation.

HONESTY NOTE
------------
This detects parcel outlines in a scanned map image. It does NOT georeference
them. The previous implementation mapped pixels to latitude/longitude with
`lng = 80.05 + (px/width) * 0.015` — an arbitrary linear stretch anchored to a
fixed point near Bilhaur, with no control points and no CRS — invented khasra
numbers as `450 + index`, attached a 0.94 confidence literal, and silently
returned a synthetic six-parcel village map when detection failed
(ARCHITECTURE_AUDIT §4.13).

All four behaviours are removed. Output is in normalised image coordinates,
labelled VECTORIZED_UNGEOREFERENCED, and detection failure is an error.
"""
from typing import Any, Dict, List

import cv2

from app.core.errors import ImagePreprocessError, ProcessingError


class CadastralVectorizationError(ProcessingError):
    code = "CADASTRAL_VECTORIZATION_FAILED"
    stage = "vectorize"


class CadastralMapService:
    MIN_AREA_FRACTION = 0.002
    MAX_AREA_FRACTION = 0.40

    def process_cadastral_map(self, image_path: str) -> Dict[str, Any]:
        img = cv2.imread(image_path)
        if img is None:
            raise ImagePreprocessError(
                "The uploaded map sheet could not be read as an image.",
                details={"path": image_path},
            )

        height, width = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        page_area = float(width * height)
        parcels: List[Dict[str, Any]] = []

        for contour in contours:
            area_px = cv2.contourArea(contour)
            if not (page_area * self.MIN_AREA_FRACTION < area_px < page_area * self.MAX_AREA_FRACTION):
                continue
            approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
            if len(approx) < 3:
                continue

            # Normalised image coordinates in [0,1]. NOT longitude/latitude.
            ring = [[round(float(pt[0][0]) / width, 6), round(float(pt[0][1]) / height, 6)] for pt in approx]
            ring.append(ring[0])

            parcels.append(
                {
                    "type": "Feature",
                    "properties": {
                        # No khasra number is assigned. Reading plot numbers off a
                        # naksha is a separate OCR task that has not been run here.
                        "khasra_number": None,
                        "label_source": "not_extracted",
                        "area_image_fraction": round(area_px / page_area, 6),
                        "vertices": len(approx),
                        "geometry_source": "VECTORIZED_UNGEOREFERENCED",
                        "coordinate_space": "normalised_image_xy",
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )

        if not parcels:
            raise CadastralVectorizationError(
                "No parcel outlines were detected in this map sheet.",
                details={
                    "image_size": [width, height],
                    "contours_examined": len(contours),
                    "likely_causes": [
                        "the sheet is faint, noisy, or low resolution",
                        "boundaries are broken or hand-drawn too lightly",
                        "the image is not a cadastral map sheet",
                    ],
                },
            )

        return {
            "status": "success",
            "parcels_detected": len(parcels),
            "georeferenced": False,
            "coordinate_space": "normalised_image_xy",
            "warning": (
                "These outlines are traced from image pixels and are NOT georeferenced. "
                "Georeferencing requires survey control points. Do not overlay on a basemap "
                "or treat as cadastral boundaries until control points are supplied."
            ),
            "image_size": {"width": width, "height": height},
            "geojson": {"type": "FeatureCollection", "features": parcels},
        }


cadastral_map_service = CadastralMapService()
