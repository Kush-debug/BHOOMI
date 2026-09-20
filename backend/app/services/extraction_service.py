"""
Structured land-record field extraction from real OCR output.

Two rules govern this module (BHUMI_FORENSICS_SPEC §2):

1. No bounding box is ever invented. A field gets geometry only when its value is
   matched back to actual Tesseract word boxes. Otherwise bbox is None and
   bbox_source is "NONE", and the UI says so.
2. Confidence is derived from the OCR that produced the text, and validation may
   only *lower* it. Nothing in this file returns a confidence literal.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.utils.terminology import TERMINOLOGY_DICTIONARY, normalize_area_unit

# Provenance of an extracted field value.
PROV_DOCUMENT_OCR = "DOCUMENT_OCR"
PROV_UPLOAD_METADATA = "UPLOAD_METADATA"
PROV_OFFICER = "OFFICER_CORRECTION"

# Where a bounding box came from.
BBOX_OCR_WORDS = "OCR_WORD_BOX"
BBOX_NONE = "NONE"

# Format expectations used only to *penalise* implausible values.
_FORMAT_CHECKS = {
    "khasra_number": re.compile(r"^[0-9]+(?:[/-][0-9A-Za-z]+)*$"),
    "khata_number": re.compile(r"^[0-9]+(?:[/-][0-9A-Za-z]+)*$"),
    "survey_number": re.compile(r"^[0-9]+(?:[/-][0-9A-Za-z]+)*$"),
    "mutation_number": re.compile(r"^[0-9A-Za-z][0-9A-Za-z/\-]{1,40}$"),
    "registration_number": re.compile(r"^[0-9A-Za-z][0-9A-Za-z/\-]{1,40}$"),
}

MULTILINGUAL_PATTERNS: Dict[str, List[Tuple[str, str, str]]] = {
    "ta": [
        ("owner_name", r"உரிமையாளர்\s*பெயர்\s*[:\-]\s*([^\n|]+)", "உரிமையாளர் பெயர் (Owner Name)"),
        ("father_name", r"தந்தை\s*பெயர்\s*[:\-]\s*([^\n|]+)", "தந்தை பெயர் (Father Name)"),
        ("khasra_number", r"புல\s*எண்(?:\s*/\s*உட்பிரிவு)?\s*[:\-]\s*([0-9/\-]+)", "புல எண் (Survey / Sub-div)"),
        ("khata_number", r"பட்டா\s*எண்\s*[:\-]\s*([0-9/\-]+)", "பட்டா எண் (Patta Number)"),
        ("area", r"பரப்பளவு\s*[:\-]\s*([0-9.]+)", "பரப்பளவு (Area Extent)"),
        ("land_classification", r"நில\s*வகைப்பாடு\s*[:\-]\s*([^\n|]+)", "நில வகைப்பாடு (Classification)"),
        ("registration_number", r"பதிவு\s*எண்\s*[:\-]\s*([A-Z0-9\-/]+)", "பதிவு எண் (Registration No)"),
    ],
    "te": [
        ("owner_name", r"పట్టాదారు\s*పేరు\s*[:\-]\s*([^\n|]+)", "పట్టాదారు పేరు (Pattadar / Owner)"),
        ("father_name", r"తండ్రి\s*పేరు\s*[:\-]\s*([^\n|]+)", "తండ్రి పేరు (Father Name)"),
        ("khasra_number", r"సర్వే\s*నెంబరు(?:\s*/\s*సబ్\s*డివిజన్)?\s*[:\-]\s*([0-9/\-]+)", "సర్వే నెంబరు (Survey No)"),
        ("khata_number", r"ఖాతా\s*నెంబరు\s*[:\-]\s*([0-9/\-]+)", "ఖాతా నెంబరు (Khata No)"),
        ("area", r"విస్తీర్ణము\s*[:\-]\s*([0-9.]+)", "విస్తీర్ణము (Area Extent)"),
        ("land_classification", r"భూమి\s*రకం\s*[:\-]\s*([^\n|]+)", "భూమి రకం (Land Classification)"),
    ],
    "kn": [
        ("owner_name", r"ಖಾತೇದಾರರ\s*ಹೆಸರು\s*[:\-]\s*([^\n|]+)", "ಖಾತೇದಾರರ ಹೆಸರು (Owner Name)"),
        ("father_name", r"ತಂದೆಯ\s*ಹೆಸರು\s*[:\-]\s*([^\n|]+)", "ತಂದೆಯ ಹೆಸರು (Father Name)"),
        ("khasra_number", r"ಸರ್ವೆ\s*ನಂಬರ್(?:\s*/\s*ಹಿಸ್ಸಾ)?\s*[:\-]\s*([0-9/\-]+)", "ಸರ್ವೆ ನಂಬರ್ (Survey / Hissa)"),
        ("khata_number", r"ಖಾತಾ\s*ಸಂಖ್ಯೆ\s*[:\-]\s*([0-9/\-]+)", "ಖಾತಾ ಸಂಖ್ಯೆ (Khata No)"),
        ("area", r"ವಿಸ್ತೀರ್ಣ\s*[:\-]\s*([0-9.]+)", "ವಿಸ್ತೀರ್ಣ (Area Extent)"),
        ("land_classification", r"ಜಮೀನಿನ\s*ವಿವರ\s*[:\-]\s*([^\n|]+)", "ಜಮೀನಿನ ವಿವರ (Classification)"),
    ],
}

# Fields whose presence means "this really is a land record".
CORE_LAND_FIELDS = {"khasra_number", "khata_number", "survey_number", "owner_name", "area"}

# Column headers for tabular layouts (e.g. UP Bhulekh खतौनी) where a value
# sits in a table cell below a column heading rather than beside an inline
# "label: value" pair. Matched against a whole OCR line's text -- no capture
# group, this only locates *where the column is*, not its values.
_TABLE_TARGET_MARKERS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("owner_name", re.compile(r"खातेदार|भूस्वामी|काश्तकार")),
    ("khasra_number", re.compile(r"खसरा\s*(?:नं\.?|संख्या|नंबर)|गाटा\s*(?:नं\.?|संख्या)")),
    ("area", re.compile(r"क्षेत्रफल|रकबा")),
]
# Non-target columns (order / remarks) whose header we also locate, purely so
# their body text repels nearest-column assignment instead of leaking into a
# target column's values.
_TABLE_IGNORE_MARKERS: List["re.Pattern[str]"] = [
    re.compile(r"आदेश"),
    re.compile(r"टिप्पणी"),
]
_TABLE_ROW_STOP = re.compile(r"^\s*(?:योग|कुल|total)\b", re.IGNORECASE)
_TABLE_HEADER_MAX_WORDS = 8  # a header cell is short; a body paragraph is not
_TABLE_BODY_MAX_WORDS = 12  # a table cell, even a wrapped one, is short too
_TABLE_MAX_ROWS = 80  # sanity cap so a false-positive header can't walk the whole page


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text)).strip().lower()


class ExtractionService:
    def extract_structured_fields(
        self,
        raw_text: str,
        ocr_blocks: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
        detected_lang: str = "en",
        page_mean_confidence: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Extract canonical land fields from OCR text.

        `ocr_blocks` are real Tesseract word boxes. `page_mean_confidence` is the
        real mean word confidence of the OCR run and is the ceiling for any field
        that cannot be grounded to specific words.
        """
        meta = metadata or {}
        extracted: List[Dict[str, Any]] = []
        found: set = set()

        def add(field_key: str, value: str, display: str, source_text: str) -> None:
            value = re.sub(r"[\t\r\n|]+", " ", str(value)).strip()
            if not value:
                return
            if field_key == "area_unit":
                value = normalize_area_unit(value)
            elif field_key == "area":
                try:
                    value = str(float(value))
                except ValueError:
                    pass

            bbox, bbox_source, matched_conf, page_no, matched_blocks = self._ground_in_ocr(value, ocr_blocks)
            confidence = self._confidence_for(
                field_key=field_key,
                value=value,
                matched_confidence=matched_conf,
                page_mean_confidence=page_mean_confidence,
            )
            extracted.append(
                {
                    "field_name": display,
                    "standardized_field": field_key,
                    "field_value": value,
                    "confidence": confidence,
                    "confidence_basis": (
                        "mean OCR word confidence of the matched region"
                        if bbox_source == BBOX_OCR_WORDS
                        else "page mean OCR confidence (value not matched to specific words)"
                    ),
                    "source_text": source_text,
                    "page_number": page_no,
                    "bounding_box": bbox,          # None when OCR gave no geometry
                    "bbox_source": bbox_source,
                    "provenance": PROV_DOCUMENT_OCR,
                    "status": "auto_extracted",
                    # First OCR word backing this value, for linking to its
                    # EvidenceRegion row (app/api/v1/processing.py). Not a
                    # model field — stripped before Claim(**kwargs).
                    "_evidence_anchor": (
                        {
                            "page_number": matched_blocks[0].get("page_number"),
                            "line_num": matched_blocks[0].get("line_num"),
                            "block_num": matched_blocks[0].get("block_num"),
                            "text": matched_blocks[0].get("text"),
                        }
                        if matched_blocks
                        else None
                    ),
                }
            )
            found.add(field_key)

        # 1. Script-specific patterns.
        for field_key, pattern, display in MULTILINGUAL_PATTERNS.get(detected_lang, []):
            m = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if m:
                add(field_key, m.group(1), display, m.group(0))

        # 2. Shared terminology dictionary (Hindi / English / state overlays).
        for field_key, field_def in TERMINOLOGY_DICTIONARY.items():
            if field_key in found:
                continue
            pattern = field_def.get("regex")
            if not pattern:
                continue
            m = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
            if m:
                add(field_key, m.group(1), field_def["display_name_en"], m.group(0))

        # 2b. Tabular layouts: some documents put khasra/owner/area under a
        # column heading instead of beside an inline label (see
        # _extract_table_fields). A table can legitimately yield several rows
        # for the same field, so every match is added -- this does not check
        # `found` and does not stop at one.
        for field_key, value, source_text in self._extract_table_fields(ocr_blocks):
            add(field_key, value, TERMINOLOGY_DICTIONARY[field_key]["display_name_en"], source_text)

        # 3. Administrative location.
        #
        # These come from the upload form, NOT from the document. They used to be
        # emitted as auto-extracted fields at 0.98 confidence, which is a claim the
        # document does not support. They are still useful, so they are kept and
        # explicitly labelled UPLOAD_METADATA with no bounding box.
        for key, display in (
            ("state", "State / राज्य"),
            ("district", "District / जनपद"),
            ("tehsil", "Tehsil / तहसील"),
            ("village", "Village / ग्राम"),
        ):
            if key in found:
                continue
            value = meta.get(key)
            if not value:
                continue
            extracted.append(
                {
                    "field_name": display,
                    "standardized_field": key,
                    "field_value": str(value),
                    "confidence": None,
                    "confidence_basis": "not extracted from the document; supplied on the upload form",
                    "source_text": None,
                    "page_number": None,
                    "bounding_box": None,
                    "bbox_source": BBOX_NONE,
                    "provenance": PROV_UPLOAD_METADATA,
                    "status": "from_upload_metadata",
                }
            )

        return extracted

    # -- helpers ------------------------------------------------------------

    def _extract_table_fields(self, ocr_blocks: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
        """Pull values out of a table where they sit under a column heading
        instead of beside an inline label (khasra/owner/area in a खतौनी table).

        Column position comes from real OCR word geometry only -- no cell is
        invented. Rows are never paired across columns: a wrapped khasra cell
        and the owner name in the next column are each emitted as their own
        value, never asserted as belonging to the same person, because word
        position alone cannot reliably prove that link. The officer sees each
        one highlighted in the original scan and makes that call.

        Returns a list of (field_key, value, source_text) tuples -- typically
        several per field on a real table, one per row.
        """
        if not ocr_blocks:
            return []

        by_page: Dict[Any, List[Dict[str, Any]]] = {}
        for b in ocr_blocks:
            by_page.setdefault(b.get("page_number"), []).append(b)

        out: List[Tuple[str, str, str]] = []
        for page_blocks in by_page.values():
            out.extend(self._extract_table_fields_one_page(page_blocks))
        return out

    @staticmethod
    def _extract_table_fields_one_page(blocks: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
        # Re-group words into OCR lines (Tesseract usually gives a bordered
        # table cell its own block_num, so a header row's columns typically
        # arrive as separate lines at roughly the same height, not one line).
        lines: Dict[Tuple[Any, Any], List[Dict[str, Any]]] = {}
        for b in blocks:
            key = (b.get("block_num"), b.get("line_num"))
            lines.setdefault(key, []).append(b)

        rows = []
        for words in lines.values():
            words = sorted(words, key=lambda w: w["bbox"][0])
            text = " ".join(w["text"] for w in words)
            if not text.strip():
                continue
            xs = [w["bbox"][0] + w["bbox"][2] / 2 for w in words]
            tops = [w["bbox"][1] for w in words]
            bottoms = [w["bbox"][1] + w["bbox"][3] for w in words]
            rows.append(
                {
                    "words": words,
                    "text": text,
                    "x_center": sum(xs) / len(xs),
                    "y_top": min(tops),
                    "y_bottom": max(bottoms),
                }
            )
        rows.sort(key=lambda r: r["y_top"])
        if not rows:
            return []

        # Candidate header cells: short lines matching a target or ignore
        # marker. A body cell can accidentally contain one of these words too
        # (an order-column row starting "...अदेश श्रीमान्..." matches
        # "आदेश"), so a single isolated hit is not enough -- only a cluster
        # of hits at nearly the same height, the way real column headers sit
        # in one table row, is accepted below.
        row_heights = [r["y_bottom"] - r["y_top"] for r in rows if r["y_bottom"] > r["y_top"]]
        row_heights.sort()
        median_height = row_heights[len(row_heights) // 2] if row_heights else 20
        y_tolerance = max(10, median_height * 1.5)

        candidates: List[Dict[str, Any]] = []
        for row in rows:
            if len(row["words"]) > _TABLE_HEADER_MAX_WORDS:
                continue
            target = next((fk for fk, pat in _TABLE_TARGET_MARKERS if pat.search(row["text"])), None)
            is_ignore = any(pat.search(row["text"]) for pat in _TABLE_IGNORE_MARKERS)
            if target is None and not is_ignore:
                continue
            candidates.append({"field_key": target, "x_center": row["x_center"], "y_top": row["y_top"], "y_bottom": row["y_bottom"]})

        # Cluster candidates by y-proximity; a real header row clusters
        # several distinct markers within one row's height of each other.
        clusters: List[List[Dict[str, Any]]] = []
        for cand in sorted(candidates, key=lambda c: c["y_top"]):
            placed = False
            for cluster in clusters:
                if abs(cand["y_top"] - cluster[-1]["y_top"]) <= y_tolerance:
                    cluster.append(cand)
                    placed = True
                    break
            if not placed:
                clusters.append([cand])

        if not clusters:
            return []
        # Prefer the cluster covering the most distinct target fields; ties
        # broken by whichever appears first (a header precedes its table).
        best = max(
            clusters,
            key=lambda cl: (len({c["field_key"] for c in cl if c["field_key"]}), -cl[0]["y_top"]),
        )
        anchors: List[Tuple[Optional[str], float]] = [(c["field_key"], c["x_center"]) for c in best]
        target_anchors = [a for a in anchors if a[0] is not None]
        if not target_anchors:
            return []
        header_bottom = max(c["y_bottom"] for c in best)

        # The योग/total row is the intended stop signal, but it is itself OCR
        # text and can get corrupted on a noisy scan just like anything else
        # -- if it never matches, this must not silently walk into whatever
        # comes after the table (disclaimer boilerplate, in every UP Bhulekh
        # extract, has no column structure at all and would otherwise get
        # tagged as owner_name/area). Two independent, OCR-content-agnostic
        # guards back the keyword check up:
        #  - a large vertical jump from the previous row -- real table rows
        #    (including a khasra cell wrapped across sub-lines) sit close
        #    together; a jump past ~5 row-heights means the table ended and
        #    there is real whitespace before whatever follows.
        #  - a long row -- a table cell is a few words; a disclaimer sentence
        #    is not, regardless of what language or script it OCR'd as.
        max_gap = max(40, median_height * 5)

        out: List[Tuple[str, str, str]] = []
        body_rows = [r for r in rows if r["y_top"] > header_bottom][:_TABLE_MAX_ROWS]
        prev_bottom = header_bottom
        for row in body_rows:
            if _TABLE_ROW_STOP.match(row["text"]):
                break
            if row["y_top"] - prev_bottom > max_gap:
                break
            prev_bottom = row["y_bottom"]
            if len(row["words"]) > _TABLE_BODY_MAX_WORDS:
                continue
            field_key, _ = min(anchors, key=lambda a: abs(a[1] - row["x_center"]))
            if field_key is None:
                continue
            value = row["text"].strip()
            if value:
                out.append((field_key, value, value))
        return out

    def _ground_in_ocr(
        self, value: str, ocr_blocks: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, int]], str, Optional[float], Optional[int], List[Dict[str, Any]]]:
        """Match an extracted value back to the OCR words that produced it.

        Returns (bbox | None, bbox_source, mean confidence of matched words | None,
        page number | None, matched OCR word blocks | []). Returns None geometry
        when no match is found — it never guesses coordinates.
        """
        if not ocr_blocks:
            return None, BBOX_NONE, None, None, []

        target = _norm(value)
        if not target:
            return None, BBOX_NONE, None, None, []

        target_tokens = [t for t in target.split() if t]

        # Try to find a contiguous run of words on one line covering the value.
        best: List[Dict[str, Any]] = []
        for i, block in enumerate(ocr_blocks):
            if _norm(block.get("text", "")) != target_tokens[0]:
                continue
            run = [block]
            ok = True
            for offset, tok in enumerate(target_tokens[1:], start=1):
                if i + offset >= len(ocr_blocks):
                    ok = False
                    break
                nxt = ocr_blocks[i + offset]
                if nxt.get("line_num") != block.get("line_num") or _norm(nxt.get("text", "")) != tok:
                    ok = False
                    break
                run.append(nxt)
            if ok:
                best = run
                break

        # Single-token containment fallback (handles trailing punctuation only).
        if not best and len(target_tokens) == 1:
            for block in ocr_blocks:
                bt = _norm(block.get("text", ""))
                if bt and (bt == target or bt.strip(".,;:।") == target):
                    best = [block]
                    break

        if not best:
            return None, BBOX_NONE, None, None, []

        xs = [b["bbox"][0] for b in best]
        ys = [b["bbox"][1] for b in best]
        x2 = [b["bbox"][0] + b["bbox"][2] for b in best]
        y2 = [b["bbox"][1] + b["bbox"][3] for b in best]
        confs = [float(b.get("confidence", 0.0)) for b in best]

        bbox = {
            "x": int(min(xs)),
            "y": int(min(ys)),
            "w": int(max(x2) - min(xs)),
            "h": int(max(y2) - min(ys)),
        }
        return (
            bbox,
            BBOX_OCR_WORDS,
            round(sum(confs) / len(confs), 4),
            best[0].get("page_number"),
            best,
        )

    def _confidence_for(
        self,
        field_key: str,
        value: str,
        matched_confidence: Optional[float],
        page_mean_confidence: Optional[float],
    ) -> Optional[float]:
        """Confidence = OCR evidence, optionally penalised. Never invented.

        - Grounded to words  -> mean confidence of those words.
        - Not grounded       -> page mean OCR confidence (a weaker but real basis).
        - Neither available  -> None. The UI shows 'unknown', not a number.
        A failed format check multiplies the value down; nothing raises it.
        """
        base = matched_confidence if matched_confidence is not None else page_mean_confidence
        if base is None:
            return None

        checker = _FORMAT_CHECKS.get(field_key)
        if checker and not checker.match(value.strip()):
            base = base * settings.FORMAT_MISMATCH_PENALTY
        if field_key == "area":
            try:
                if float(value) <= 0:
                    base = base * settings.FORMAT_MISMATCH_PENALTY
            except ValueError:
                base = base * settings.FORMAT_MISMATCH_PENALTY

        return round(max(0.0, min(1.0, base)), 4)

    @staticmethod
    def has_land_record_signal(extracted: List[Dict[str, Any]]) -> bool:
        """True when the document actually looks like a land record.

        Location metadata alone does not count: it comes from the upload form.
        """
        return any(
            f["standardized_field"] in CORE_LAND_FIELDS
            and f.get("provenance") == PROV_DOCUMENT_OCR
            for f in extracted
        )


extraction_service = ExtractionService()
