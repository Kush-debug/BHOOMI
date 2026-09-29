import re
from typing import Dict, Any, List, Optional

from app.core.errors import TranslationUnavailableError

# Multi-lingual Dictionary for Key Indian Land Record Headings & Classifications
TERM_TRANSLATIONS = {
    # Land Classifications
    "Agricultural": {
        "hi": "कृषि भूमि (सिंचित / दो-फसली)",
        "ta": "விவசாய நிலம் (நஞ்சை / புஞ்சை)",
        "te": "వ్యవసాయ భూమి (మాగాణి / మెట్ట)",
        "kn": "ಕೃಷಿ ಭೂಮಿ (ತರಿ / ಖುಷ್ಕಿ)",
        "mr": "बागायती / जिरायती शेतजमीन",
        "en": "Agricultural Land (Irrigated / Dry)"
    },
    "Residential": {
        "hi": "आवासीय भूमि",
        "ta": "குடியிருப்பு நிலம்",
        "te": "నివాస స్థలము",
        "kn": "ವಸತಿ ಭೂಮಿ",
        "mr": "निवासी जमीन",
        "en": "Residential Plot"
    },
    "Commercial": {
        "hi": "व्यावसायिक भूमि",
        "ta": "வணிக நிலம்",
        "te": "వాణిజ్య భూమి",
        "kn": "ವಾಣಿಜ್ಯ ಭೂಮಿ",
        "mr": "व्यावसायिक जमीन",
        "en": "Commercial Land"
    },
    "Government / Gram Sabha": {
        "hi": "ग्राम सभा / सरकारी भूमि",
        "ta": "அரசு புறம்போக்கு நிலம்",
        "te": "ప్రభుత్వ / గ్రామ కంఠం భూమి",
        "kn": "ಸರ್ಕಾರಿ / ಗೋಮಾಳ ಭೂಮಿ",
        "mr": "शासकीय / गायरान जमीन",
        "en": "Government / Village Common Land"
    },
    # Area Units
    "hectare": {
        "hi": "हेक्टेयर",
        "ta": "ஹெக்டேர்",
        "te": "హెక్టార్",
        "kn": "ಹೆಕ್ಟೇರ್",
        "mr": "हेक्टर",
        "en": "hectare"
    },
    "acre": {
        "hi": "एकड़",
        "ta": "ஏக்கர்",
        "te": "ఎకరం",
        "kn": "ಎಕರೆ",
        "mr": "एकर",
        "en": "acre"
    },
    "bigha": {
        "hi": "बीघा",
        "ta": "பீகா",
        "te": "బిఘా",
        "kn": "ಬಿಘಾ",
        "mr": "बिघा",
        "en": "bigha"
    },
    "cent": {
        "hi": "सेंट",
        "ta": "சென்ட்",
        "te": "సెంట్",
        "kn": "ಸೆಂಟ್",
        "mr": "गुंठा",
        "en": "cent"
    }
}

# Personal Names Known Mappings & Transliteration
NAME_TRANSLATIONS = {
    # Tamil Names
    "ராமசாமி": {"en": "Ramasamy", "hi": "रामसामी", "te": "రామస్వామి", "kn": "ರಾಮಸ್ವಾಮಿ"},
    "முருகன்": {"en": "Murugan", "hi": "मुरुगन", "te": "మురుగన్", "kn": "ಮುರುಗನ್"},
    "கந்தசாமி": {"en": "Kandasamy", "hi": "कंदसामी", "te": "కందస్వామి", "kn": "ಕಂದಸ್ವಾಮಿ"},
    "செல்வி": {"en": "Selvi", "hi": "सेल्वी", "te": "సెల్వి", "kn": "ಸೆಲ್ವಿ"},
    "சுப்ரமணியன்": {"en": "Subramanian", "hi": "सुब्रमण्यन", "te": "సుబ్రమణ్యన్", "kn": "ಸುಬ್ರಮಣ್ಯನ್"},
    
    # Telugu Names
    "వెంకటేశ్వర్లు": {"en": "Venkateswarlu", "hi": "वेंकटेश्वरलू", "ta": "வெங்கடேஸ்வரலு", "kn": "ವೆಂಕಟೇಶ್ವರಲು"},
    "సత్యనారాయణ": {"en": "Satyanarayana", "hi": "सत्यनारायण", "ta": "சத்யநாராயணா", "kn": "ಸತ್ಯನಾರಾಯಣ"},
    "లక్ష్మి": {"en": "Lakshmi", "hi": "लक्ष्मी", "ta": "லட்சுமி", "kn": "ಲಕ್ಷ್ಮಿ"},

    # Kannada Names
    "ಮಂಜುನಾಥ್": {"en": "Manjunath", "hi": "मंजूनाथ", "ta": "மஞ்சுநாத்", "te": "మంజునాథ్"},
    "ಬಸವರಾಜ್": {"en": "Basavaraj", "hi": "बसवराज", "ta": "பசவராஜ்", "te": "బసవరాజు"},
    "ಸಿದ್ಧಲಿಂಗಯ್ಯ": {"en": "Siddalingaiah", "hi": "सिद्धलिंगैया", "ta": "சித்தலிங்கய்யா", "te": "సిద్ధలింగయ్య"},

    # Hindi Names
    "राम प्रसाद": {"en": "Ram Prasad", "hi": "राम प्रसाद", "ta": "ராம் பிரசாத்", "te": "రామ్ ప్రసాద్", "kn": "ರಾಮ್ ಪ್ರಸಾದ್"},
    "श्याम सुंदर": {"en": "Shyam Sundar", "hi": "श्याम सुंदर", "ta": "ஷ்யாம் சுந்தர்", "te": "శ్యామ్ సుందర్", "kn": "ಶ್ಯಾಮ್ ಸುಂದರ್"},
    "सुरेश कुमार": {"en": "Suresh Kumar", "hi": "सुरेश कुमार", "ta": "சுரேஷ் குமார்", "te": "సురేష్ కుమార్", "kn": "ಸುರೇಶ್ ಕುಮಾರ್"},
    "राधे मोहन": {"en": "Radhey Mohan", "hi": "राधे मोहन", "ta": "ராதே மோகன்", "te": "రాధే మోహన్", "kn": "ರಾಧೇ ಮೋಹನ್"},
    "अनिता देवी": {"en": "Anita Devi", "hi": "अनिता देवी", "ta": "அனிதா தேவி", "te": "అనితా దేవి", "kn": "ಅನಿತಾ ದೇವಿ"},
    "महेश कुमार": {"en": "Mahesh Kumar", "hi": "महेश कुमार", "ta": "மகேஷ் குமார்", "te": "మహేష్ కుమార్", "kn": "ಮಹೇಶ್ ಕುಮಾರ್"}
}

# Protected Identifier Fields that must NEVER be altered or phonetically corrupted
PROTECTED_IDENTIFIER_FIELDS = {
    "survey_number",
    "khasra_number",
    "khata_number",
    "khatauni_number",
    "patta_number",
    "plot_number",
    "registration_number",
    "mutation_number",
    "document_number",
    "area",
    "date",
    "coordinates"
}

class TranslationService:
    def translate_text(self, text: str, source_lang: str, target_lang: str = "en") -> Dict[str, Any]:
        """
        Translate arbitrary OCR text, not just predefined land-record terms.
        Numeric/cadastral identifiers are masked before translation and restored.
        Uses Google Translate through deep-translator for the prototype, with a
        graceful fallback to the original text if the network/provider is unavailable.
        """
        if not text or not text.strip() or target_lang == source_lang:
            return {"text": text or "", "confidence": None, "provider": "identity (no translation needed)"}

        supported = {"en", "hi", "ta", "te", "kn", "mr", "bn", "gu", "pa"}
        if target_lang not in supported:
            raise TranslationUnavailableError(
                f"Target language '{target_lang}' is not supported by the configured provider.",
                details={"supported": sorted(supported)},
            )

        # Protect survey/khata/registration/mutation identifiers and dates.
        protected = []
        patterns = [
            r"\b[A-Z]{1,8}[-/][A-Z0-9./-]{2,}\b",
            r"\b\d{1,6}(?:/\d{1,6})+(?:/[A-Z0-9]+)?\b",
            r"\b\d{1,6}[A-Z]?\b",
            r"\b\d{1,4}[/-]\d{1,2}[/-]\d{2,4}\b",
        ]

        def mask_match(m):
            token = f"__BH_ID_{len(protected)}__"
            protected.append(m.group(0))
            return token

        masked = text
        for pattern in patterns:
            masked = re.sub(pattern, mask_match, masked)

        try:
            from deep_translator import GoogleTranslator

            # Translate line-by-line to keep land-record formatting readable.
            translator = GoogleTranslator(source="auto", target=target_lang)
            chunks = []
            for line in masked.splitlines():
                if not line.strip():
                    chunks.append("")
                    continue
                # Google translation has practical per-request limits.
                parts = [line[i:i+3500] for i in range(0, len(line), 3500)]
                chunks.append("".join(translator.translate(p) or p for p in parts))

            translated = "\n".join(chunks)

            for i, original in enumerate(protected):
                translated = translated.replace(f"__BH_ID_{i}__", original)

            return {
                "text": translated,
                # MT quality is not measured here, so no number is reported for it.
                # The previous literal 0.90 was a fabricated metric.
                "confidence": None,
                "provider": "Google Translate (deep-translator)",
            }
        except Exception as exc:
            # The original OCR is never destroyed or overwritten. The caller decides
            # whether to proceed untranslated; nothing is presented as translated
            # when it was not.
            raise TranslationUnavailableError(
                f"Translation to '{target_lang}' is unavailable: {type(exc).__name__}.",
                details={
                    "provider": "deep-translator / Google Translate",
                    "target_language": target_lang,
                    "note": "The original OCR text is preserved and remains available.",
                },
            ) from exc

    def translate_field(
        self,
        field_key: str,
        original_value: str,
        source_lang: str,
        target_lang: str = "en"
    ) -> Dict[str, Any]:
        """
        Translates extracted field value to target language while strictly
        protecting numeric and cadastral identifiers.
        """
        if not original_value:
            return {
                "original_value": "",
                "translated_value": "",
                "transliteration": "",
                "translations_json": {},
                "translation_confidence": None,
                "translation_basis": "empty value",
            }

        val_clean = str(original_value).strip()

        # 1. IDENTIFIER PROTECTION: NEVER change Survey/Khasra/Khata/Area numbers
        if field_key in PROTECTED_IDENTIFIER_FIELDS:
            # Preserve exact identifier string
            translations = {lang: val_clean for lang in ["en", "hi", "ta", "te", "kn", "mr", "bn", "gu", "pa"]}
            return {
                "original_value": val_clean,
                "translated_value": val_clean,
                "transliteration": val_clean,
                "translations_json": translations,
                "translation_confidence": None,
                "translation_basis": "identifier preserved verbatim (no translation applied)",
            }

        # 2. Check Name Dictionary
        if val_clean in NAME_TRANSLATIONS:
            entry = NAME_TRANSLATIONS[val_clean]
            translit = entry.get("en", val_clean)
            target_val = entry.get(target_lang, translit)
            all_translations = {**entry, source_lang: val_clean}
            return {
                "original_value": val_clean,
                "translated_value": target_val,
                "transliteration": translit,
                "translations_json": all_translations,
                "translation_confidence": None,
                "translation_basis": "curated name dictionary",
            }

        # 3. Check Known Land Terminology (Classification, Units, etc.)
        for term, trans_dict in TERM_TRANSLATIONS.items():
            if val_clean.lower() == term.lower() or val_clean in trans_dict.values():
                target_val = trans_dict.get(target_lang, trans_dict.get("en", term))
                return {
                    "original_value": val_clean,
                    "translated_value": target_val,
                    "transliteration": term,
                    "translations_json": trans_dict,
                    "translation_confidence": None,
                    "translation_basis": "curated land terminology dictionary",
                }

        # 4. Machine translation for arbitrary values. If the provider is down we
        #    keep the original value and say so, rather than claiming a translation.
        try:
            result = self.translate_text(val_clean, source_lang, target_lang)
            target_val = result["text"]
            basis = result["provider"]
        except TranslationUnavailableError:
            target_val = val_clean
            basis = "translation unavailable - original value retained"
            result = {"confidence": None}
        translations = {
            source_lang: val_clean,
            target_lang: target_val,
            "en": val_clean if source_lang == "en" else val_clean
        }

        return {
            "original_value": val_clean,
            "translated_value": target_val,
            "transliteration": val_clean,
            "translations_json": translations,
            "translation_confidence": result.get("confidence"),
            "translation_basis": basis,
        }

    def generate_multilingual_representations(
        self,
        extracted_fields: List[Dict[str, Any]],
        source_lang: str,
        target_lang: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Processes each extracted field to attach protected translations,
        transliterations, and multi-language dictionary representations.
        """
        enriched = []
        for f in extracted_fields:
            field_key = f.get("standardized_field", "")
            raw_val = f.get("field_value", "")
            
            trans_res = self.translate_field(field_key, raw_val, source_lang, target_lang)

            item = dict(f)
            item["original_value"] = trans_res["original_value"]
            item["translated_value"] = trans_res["translated_value"]
            item["transliteration"] = trans_res["transliteration"]
            item["translations_json"] = trans_res["translations_json"]
            
            # If target language requested is different, display translated value as primary
            if target_lang == "en" and trans_res["translated_value"]:
                item["field_value"] = trans_res["translated_value"]
            else:
                item["field_value"] = trans_res["translations_json"].get(target_lang, trans_res["original_value"])

            # Only components we actually measured. Unmeasured components are
            # reported as null and the UI renders them as "not available".
            item["confidence_breakdown"] = {
                "extraction": f.get("confidence"),
                "extraction_basis": f.get("confidence_basis"),
                "translation": trans_res.get("translation_confidence"),
                "translation_basis": trans_res.get("translation_basis"),
            }
            enriched.append(item)
        return enriched

translation_service = TranslationService()
