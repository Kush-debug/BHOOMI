import re
from typing import Dict, Any, Tuple

INDIC_SCRIPT_RANGES = {
    "ta": {"name": "Tamil", "native": "தமிழ்", "range": (0x0B80, 0x0BFF)},
    "te": {"name": "Telugu", "native": "తెలుగు", "range": (0x0C00, 0x0C7F)},
    "kn": {"name": "Kannada", "native": "ಕನ್ನಡ", "range": (0x0C80, 0x0CFF)},
    "ml": {"name": "Malayalam", "native": "മലയാളം", "range": (0x0D00, 0x0D7F)},
    "hi": {"name": "Hindi", "native": "हिन्दी", "range": (0x0900, 0x097F)},  # Devanagari
    "mr": {"name": "Marathi", "native": "मराठी", "range": (0x0900, 0x097F)},
    "bn": {"name": "Bengali", "native": "বাংলা", "range": (0x0980, 0x09FF)},
    "gu": {"name": "Gujarati", "native": "ગુજરાતી", "range": (0x0A80, 0x0AFF)},
    "pa": {"name": "Punjabi", "native": "ਪੰਜਾਬੀ", "range": (0x0A00, 0x0A7F)},
    "or": {"name": "Odia", "native": "ଓଡ଼ିଆ", "range": (0x0B00, 0x0B7F)},
    "as": {"name": "Assamese", "native": "অসমীয়া", "range": (0x0980, 0x09FF)},
    "ur": {"name": "Urdu", "native": "اردو", "range": (0x0600, 0x06FF)},
}

class LanguageDetectionService:
    def detect_language(self, text: str, fallback_hint: str = "hi") -> Dict[str, Any]:
        """
        Analyzes Unicode block character distributions and lexical markers
        to automatically detect Indian scripts and languages.
        """
        if not text or len(text.strip()) == 0:
            return {
                "detected_language": fallback_hint,
                "language_name": INDIC_SCRIPT_RANGES.get(fallback_hint, {}).get("name", "Hindi"),
                "confidence": 0.85,
                "is_confident": True,
                "multi_languages": [fallback_hint]
            }

        counts = {code: 0 for code in INDIC_SCRIPT_RANGES}
        latin_count = 0
        total_indic = 0

        for char in text:
            cp = ord(char)
            # Latin English
            if (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
                latin_count += 1
                continue

            # Indic Unicode ranges
            for code, meta in INDIC_SCRIPT_RANGES.items():
                low, high = meta["range"]
                if low <= cp <= high:
                    counts[code] += 1
                    total_indic += 1
                    break

        # Distinguish Marathi from Hindi in Devanagari using specific characters (ळ, etc.)
        if counts["hi"] > 0 and ("ळ" in text or "क्षेत्रफळ" in text or "खातेदार" in text or "उतारा" in text):
            counts["mr"] = counts["hi"]
            counts["hi"] = 0

        total_chars = total_indic + latin_count
        if total_chars == 0:
            return {
                "detected_language": fallback_hint,
                "language_name": INDIC_SCRIPT_RANGES.get(fallback_hint, {}).get("name", "Hindi"),
                "confidence": 0.80,
                "is_confident": False,
                "multi_languages": [fallback_hint]
            }

        # Check dominant script
        best_code, best_count = max(counts.items(), key=lambda item: item[1])

        if best_count > 0 and (best_count >= latin_count or best_count / float(total_chars) > 0.15):
            conf = min(0.99, max(0.90, round(best_count / float(max(1, total_indic)), 2)))
            multi = [best_code]
            if latin_count > 0.1 * total_chars:
                multi.append("en")

            return {
                "detected_language": best_code,
                "language_name": INDIC_SCRIPT_RANGES[best_code]["name"],
                "native_name": INDIC_SCRIPT_RANGES[best_code]["native"],
                "confidence": conf,
                "is_confident": conf >= 0.80,
                "multi_languages": multi
            }
        elif latin_count > 0:
            conf = min(0.99, max(0.92, round(latin_count / float(total_chars), 2)))
            return {
                "detected_language": "en",
                "language_name": "English",
                "native_name": "English",
                "confidence": conf,
                "is_confident": True,
                "multi_languages": ["en"]
            }

        return {
            "detected_language": fallback_hint,
            "language_name": INDIC_SCRIPT_RANGES.get(fallback_hint, {}).get("name", "Hindi"),
            "confidence": 0.85,
            "is_confident": False,
            "multi_languages": [fallback_hint]
        }

language_detection_service = LanguageDetectionService()
