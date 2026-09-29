import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.core.errors import ImagePreprocessError

def preprocess_image_for_ocr(image_path: str, output_path: str) -> dict:
    """
    Fast & robust OpenCV document enhancement pipeline:
    1. Grayscale conversion
    2. Quick Deskew estimation
    3. CLAHE Contrast enhancement
    4. Fast Gaussian noise reduction
    5. Adaptive Otsu Thresholding
    """
    if not os.path.exists(image_path):
        # Previously this wrote a blank white canvas and reported five completed
        # preprocessing stages, so a missing page silently became "a processed
        # page". A missing input is an error.
        raise ImagePreprocessError(
            "The page image to preprocess does not exist on disk.",
            details={"image_path": image_path},
        )

    img = cv2.imread(image_path)
    if img is None:
        pil_img = Image.open(image_path).convert("RGB")
        img = np.array(pil_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    height, width = img.shape[:2]

    # 1. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 2. Deskew. The docstring claimed "Quick Deskew estimation" but no deskew
    #    was performed. This estimates the dominant text angle and rotates.
    skew_angle = _estimate_skew(gray)
    if abs(skew_angle) > 0.3:
        matrix = cv2.getRotationMatrix2D((gray.shape[1] / 2, gray.shape[0] / 2), skew_angle, 1.0)
        gray = cv2.warpAffine(
            gray, matrix, (gray.shape[1], gray.shape[0]),
            flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE,
        )

    # 2. CLAHE (Fast & Effective for Indian Revenue Records)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 3. Gaussian Blur (Fast Denoising)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # 4. Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 11
    )

    # Save enhanced image
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(output_path, thresh)

    return {
        "width": width,
        "height": height,
        "skew_angle": round(float(skew_angle), 3),
        "preprocessed_path": output_path,
        "stages": ["grayscale", "deskew", "clahe_contrast", "gaussian_denoise", "adaptive_threshold"],
    }


def _estimate_skew(gray: "np.ndarray") -> float:
    """Estimate page skew in degrees from long near-horizontal lines."""
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=120,
        minLineLength=max(60, gray.shape[1] // 6), maxLineGap=12,
    )
    if lines is None:
        return 0.0
    angles = []
    # cv2.HoughLinesP returns shape (N, 1, 4) on OpenCV < 5 and (N, 4) on
    # OpenCV >= 5; reshape normalises both to rows of [x1, y1, x2, y2].
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = np.degrees(np.arctan2(float(y2 - y1), float(x2 - x1)))
        if -20 < angle < 20:  # near-horizontal only
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))

# A phone photo saved through a chat app is often compressed down to ~1600px
# on the long side, which starves Tesseract's LSTM on small government-form
# text: verified directly -- a legible, well-lit header line OCR'd to near
# noise at native resolution, and cleanly at 2.5x. Anything already at a
# reasonable resolution is left untouched; this only helps genuinely small
# photos, and is capped so a tiny thumbnail can't be blown up into fabricated
# detail.
_UPSCALE_TARGET_LONG_SIDE = 4000
_UPSCALE_MAX_FACTOR = 3.0


def normalize_raw_image(src_path: str, dest_path: str) -> None:
    """Write the uploaded image to `dest_path`, upscaling first if it's small.

    This runs on the file that later becomes BOTH the "raw" page image served
    to the browser and the input to preprocess_image_for_ocr. Doing the
    upscale here -- once, before either of those -- keeps the raw and
    enhanced images in one shared pixel space, which matters because OCR
    bounding boxes are expressed in whichever image Tesseract actually read:
    VerificationWorkspace.jsx scales every highlight by
    `renderedWidth / DocumentPage.width`, one scale factor shared by both the
    raw and enhanced view toggle. Upscaling only inside preprocessing (after
    the raw file is already finalised) would put the two images at different
    resolutions and misalign every evidence highlight in raw view.
    """
    img = cv2.imread(src_path)
    if img is None:
        try:
            pil_img = Image.open(src_path).convert("RGB")
            img = np.array(pil_img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception:
            # Not decodable by OpenCV or PIL -- copy through untouched rather
            # than fail the upload over a display-quality enhancement.
            import shutil as _shutil

            _shutil.copyfile(src_path, dest_path)
            return

    long_side = max(img.shape[0], img.shape[1])
    if long_side < _UPSCALE_TARGET_LONG_SIDE:
        factor = min(_UPSCALE_MAX_FACTOR, _UPSCALE_TARGET_LONG_SIDE / long_side)
        img = cv2.resize(img, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)

    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest_path), img)


def detect_table_grid_and_stamps(image_path: str) -> list:
    """Detect table structure using morphological line detection.

    The previous implementation returned three boxes computed as fixed
    percentages of the image dimensions, labelled header/table/stamp with
    confidences of 0.98/0.96/0.92, without examining the image at all
    (ARCHITECTURE_AUDIT §4.6). This performs real horizontal/vertical line
    detection and returns only what it finds. An empty list means no table
    structure was detected, which is a valid and honest answer.
    """
    if not os.path.exists(image_path):
        return []

    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []

    height, width = img.shape[:2]
    binary = cv2.adaptiveThreshold(
        img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5
    )

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, width // 30), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, height // 30)))
    horizontal = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=2)
    vertical = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=2)
    grid = cv2.add(horizontal, vertical)

    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    page_area = float(width * height)
    regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if (w * h) < page_area * 0.02:
            continue
        regions.append(
            {
                "type": "table_region",
                "bbox": [int(x), int(y), int(w), int(h)],
                "detection_method": "morphological_line_detection",
                "area_fraction": round((w * h) / page_area, 4),
            }
        )
    regions.sort(key=lambda r: r["area_fraction"], reverse=True)
    return regions[:10]
