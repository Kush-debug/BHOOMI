"""
OCR service.

HISTORY / IMPORTANT
-------------------
This module previously contained a class named `HybridIndicOCREngine` which did
not read the image at all. It branched on the *upload form metadata* and returned
hand-written land-record text with hand-written bounding boxes and hand-written
confidences (0.94-0.99). `OCRService.process_image` silently fell back to it
whenever Tesseract was missing, raised, or returned short output.

That class has been deleted. It produced a fabricated Tamil Patta extract from an
uploaded resume, which is still recorded in the project audit (ARCHITECTURE_AUDIT §4.1).

There is no fallback engine. If OCR cannot run, or runs and finds nothing, this
module raises. See BHUMI_FORENSICS_SPEC §2 rules 1 and 3.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import settings
from app.core.errors import (
    OcrEmptyResultError,
    OcrEngineUnavailableError,
)
from app.services.language_detection_service import language_detection_service

# Tesseract language pack names keyed by ISO code we use internally.
_ISO_TO_TESS = {
    "en": "eng",
    "hi": "hin",
    "mr": "mar",
    "ta": "tam",
    "te": "tel",
    "kn": "kan",
    "ml": "mal",
    "bn": "ben",
    "gu": "guj",
    "pa": "pan",
    "or": "ori",
    "as": "asm",
    "ur": "urd",
}


class BaseOCREngine(ABC):
    """Contract for every OCR engine.

    Implementations MUST raise on failure. Returning plausible text for an
    unreadable page is a correctness bug, not a graceful degradation.
    """

    name: str = "base"
    version: str = "0"

    @abstractmethod
    def is_available(self) -> bool:
        ...

    @abstractmethod
    def run(
        self,
        image_path: str,
        page_number: int = 1,
        lang_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns:
        {
          raw_text: str,
          blocks: [{text, bbox:[x,y,w,h], confidence, type, line_num, page_number}],
          word_count: int,
          average_confidence: float | None,   # None when no words were read
          page_width: int, page_height: int,
          engine: str, engine_version: str, engine_langs: str,
          detected_language, detected_language_name, language_confidence
        }
        """
        ...


class TesseractEngine(BaseOCREngine):
    name = "tesseract"

    def __init__(self) -> None:
        self._pytesseract = None
        self._version = "unavailable"
        self._installed_langs: List[str] = []
        try:
            import pytesseract  # noqa: PLC0415

            self._pytesseract = pytesseract
            self._version = str(pytesseract.get_tesseract_version())
            self._installed_langs = list(pytesseract.get_languages(config=""))
        except Exception:  # ImportError, TesseractNotFoundError, OSError
            self._pytesseract = None

    # -- availability -------------------------------------------------------

    def is_available(self) -> bool:
        return self._pytesseract is not None

    @property
    def version(self) -> str:  # type: ignore[override]
        return self._version

    @property
    def installed_languages(self) -> List[str]:
        return list(self._installed_langs)

    # -- language selection -------------------------------------------------

    def _lang_string(self, lang_hint: Optional[str]) -> str:
        """Build a Tesseract -l argument from installed packs only.

        We never request a pack that is not installed: Tesseract errors out and
        the whole page would be lost.
        """
        # A usable hint (from the upload form / document language) selects ONE
        # script plus English. Loading every installed Indic pack at once makes
        # Tesseract's LSTM decode Devanagari as Tamil/Telugu/Kannada glyphs and
        # fragment tokens; run()'s detected-script second pass recovers the case
        # where the hint itself is wrong.
        if lang_hint:
            mapped = _ISO_TO_TESS.get(lang_hint, lang_hint)
            if mapped in self._installed_langs:
                if mapped == "eng" or "eng" not in self._installed_langs:
                    return mapped
                return f"{mapped}+eng"

        wanted: List[str] = []
        for iso in settings.ocr_default_languages():
            mapped = _ISO_TO_TESS.get(iso, iso)
            if mapped in self._installed_langs and mapped not in wanted:
                wanted.append(mapped)

        if not wanted:
            if "eng" in self._installed_langs:
                wanted = ["eng"]
            elif self._installed_langs:
                wanted = [self._installed_langs[0]]
            else:
                raise OcrEngineUnavailableError(
                    "Tesseract is installed but no language data packs are present.",
                    details={"hint": "Install tesseract-ocr-eng and the Indic packs you need."},
                )
        return "+".join(wanted)

    # -- execution ----------------------------------------------------------

    def run(
        self,
        image_path: str,
        page_number: int = 1,
        lang_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_available():
            raise OcrEngineUnavailableError(
                "OCR engine 'tesseract' is not available on this server.",
                details={
                    "reason": "pytesseract could not import, or the tesseract binary is not on PATH",
                    "remedy": "Install the tesseract-ocr package and its language data, then retry processing.",
                },
            )

        if not os.path.exists(image_path):
            raise OcrEmptyResultError(
                "The rendered page image is missing on disk, so OCR could not run.",
                details={"image_path": image_path, "page_number": page_number},
            )

        tess_lang = self._lang_string(lang_hint)
        result = self._ocr_pass(image_path, page_number, tess_lang)

        # Second pass: if the script we actually detected has an installed pack
        # that was not in the first pass, re-run with it. Genuinely improves
        # Indic accuracy; costs one extra pass only when the script differs.
        if settings.OCR_TWO_PASS and result["raw_text"].strip():
            detected = result["detected_language"]
            mapped = _ISO_TO_TESS.get(detected)
            if (
                mapped
                and mapped in self._installed_langs
                and mapped not in tess_lang.split("+")
            ):
                second_lang = f"{mapped}+eng" if "eng" in self._installed_langs else mapped
                second = self._ocr_pass(image_path, page_number, second_lang)
                # Keep whichever pass read more characters at higher confidence.
                if self._pass_score(second) > self._pass_score(result):
                    result = second

        text = result["raw_text"].strip()
        if len(text) < settings.OCR_MIN_CHARS:
            raise OcrEmptyResultError(
                f"OCR read {len(text)} characters from page {page_number}, "
                f"below the minimum of {settings.OCR_MIN_CHARS} needed to attempt extraction.",
                details={
                    "page_number": page_number,
                    "characters_read": len(text),
                    "engine_languages": result["engine_langs"],
                    "likely_causes": [
                        "the page is blank or contains only images",
                        "the scan quality is too low for the current preprocessing",
                        "the script on the page has no installed language pack",
                    ],
                },
            )

        return result

    @staticmethod
    def _pass_score(res: Dict[str, Any]) -> float:
        conf = res.get("average_confidence") or 0.0
        return len(res["raw_text"].strip()) * max(conf, 0.01)

    def _ocr_pass(self, image_path: str, page_number: int, tess_lang: str) -> Dict[str, Any]:
        pt = self._pytesseract
        try:
            data = pt.image_to_data(image_path, lang=tess_lang, output_type=pt.Output.DICT)
        except Exception as exc:
            raise OcrEngineUnavailableError(
                f"Tesseract failed while reading page {page_number}: {exc}",
                details={"engine_languages": tess_lang, "page_number": page_number},
            ) from exc

        page_width, page_height = self._page_size(image_path)

        blocks: List[Dict[str, Any]] = []
        conf_sum = 0.0
        word_count = 0
        lines: Dict[Any, List[str]] = {}

        for i in range(len(data["text"])):
            txt = (data["text"][i] or "").strip()
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0 or not txt:
                continue

            conf_sum += conf
            word_count += 1
            blocks.append(
                {
                    "text": txt,
                    # Real Tesseract geometry, in page-image pixel space.
                    "bbox": [
                        int(data["left"][i]),
                        int(data["top"][i]),
                        int(data["width"][i]),
                        int(data["height"][i]),
                    ],
                    "confidence": round(conf / 100.0, 4),
                    "type": "word",
                    "page_number": page_number,
                    "line_num": int(data.get("line_num", [0] * len(data["text"]))[i]),
                    "block_num": int(data.get("block_num", [0] * len(data["text"]))[i]),
                }
            )
            key = (
                data.get("block_num", [0] * len(data["text"]))[i],
                data.get("par_num", [0] * len(data["text"]))[i],
                data.get("line_num", [0] * len(data["text"]))[i],
            )
            lines.setdefault(key, []).append(txt)

        raw_text = "\n".join(" ".join(words) for _, words in sorted(lines.items(), key=lambda kv: kv[0]))

        # None, not a filler constant, when nothing was read.
        average_confidence = round(conf_sum / (word_count * 100.0), 4) if word_count else None

        lang_res = language_detection_service.detect_language(raw_text, fallback_hint="en")

        return {
            "raw_text": raw_text,
            "blocks": blocks,
            "word_count": word_count,
            "average_confidence": average_confidence,
            "page_width": page_width,
            "page_height": page_height,
            "engine": self.name,
            "engine_version": self._version,
            "engine_langs": tess_lang,
            "detected_language": lang_res["detected_language"],
            "detected_language_name": lang_res["language_name"],
            "language_confidence": lang_res["confidence"],
        }

    @staticmethod
    def _page_size(image_path: str) -> tuple:
        try:
            from PIL import Image  # noqa: PLC0415

            with Image.open(image_path) as im:
                return int(im.width), int(im.height)
        except Exception:
            return 0, 0


class OCRService:
    """Dispatches to the configured engine. There is deliberately no fallback."""

    def __init__(self) -> None:
        self.engines: Dict[str, BaseOCREngine] = {"tesseract": TesseractEngine()}

    def get_engine(self, name: Optional[str] = None) -> BaseOCREngine:
        engine = self.engines.get(name or settings.OCR_ENGINE)
        if engine is None:
            raise OcrEngineUnavailableError(
                f"OCR engine '{name or settings.OCR_ENGINE}' is not registered.",
                details={"registered": sorted(self.engines)},
            )
        return engine

    def engine_status(self) -> Dict[str, Any]:
        """Honest capability reporting for the UI and /health.

        The sidebar used to claim '13+ Indic Languages Online' regardless of what
        was installed. This returns what is actually present.
        """
        eng = self.engines["tesseract"]
        installed = eng.installed_languages if isinstance(eng, TesseractEngine) else []
        iso_available = sorted({iso for iso, t in _ISO_TO_TESS.items() if t in installed})
        return {
            "engine": eng.name,
            "available": eng.is_available(),
            "version": eng.version,
            "installed_language_packs": installed,
            "supported_iso_languages": iso_available,
            "supported_language_count": len(iso_available),
        }

    def process_page(
        self,
        image_path: str,
        page_number: int = 1,
        lang_hint: Optional[str] = None,
        engine_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run OCR on one rendered page image. Raises ProcessingError on failure."""
        return self.get_engine(engine_name).run(
            image_path=image_path, page_number=page_number, lang_hint=lang_hint
        )


ocr_service = OCRService()
