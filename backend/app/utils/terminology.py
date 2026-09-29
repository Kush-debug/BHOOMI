import re
from typing import Dict, List, Optional, Tuple

# Comprehensive State-Configurable Multi-State Terminology Dictionary
TERMINOLOGY_DICTIONARY = {
    "owner_name": {
        "standard_name": "owner_name",
        "display_name_en": "Owner Name / Landholder",
        "display_name_hi": "खातेदार का नाम / भूस्वामी",
        "aliases": [
            "खातेदार का नाम", "भूस्वामी", "पट्टेदार का नाम", "काश्तकार", "मालिक का नाम",
            "Owner Name", "Landholder", "Khatedar", "Bhooswami", "Pattadar", "Tenure Holder", "Khatedar Name"
        ],
        "regex": r"(?:खातेदार का नाम|भूस्वामी|काश्तकार|Owner\s*Name|Landholder)[:\s\-]+([^\n\r,]+)"
    },
    "father_name": {
        "standard_name": "father_name",
        "display_name_en": "Father / Husband Name",
        "display_name_hi": "पिता / पति का नाम",
        "aliases": [
            "पिता का नाम", "पति का नाम", "पिता/पति का नाम", "वालद", "Father Name", "Husband Name", "S/O", "W/O", "D/O"
        ],
        "regex": r"(?:पिता\/पति\s*का\s*नाम|पिता\s*का\s*नाम|वालद|Father(?:'s)?\s*Name|S\/O)[:\s\-]+([^\n\r,]+)"
    },
    "khasra_number": {
        "standard_name": "khasra_number",
        "display_name_en": "Khasra Number / Plot No.",
        "display_name_hi": "खसरा संख्या / गाटा संख्या",
        "aliases": [
            "खसरा नं.", "खसरा संख्या", "खसरा नंबर", "गाटा संख्या", "गाटा नं.", "खेवट", "Khasra No.",
            "Khasra Number", "Gata No.", "Gata Number", "Survey Plot", "Dag No.", "Khasra"
        ],
        "regex": r"(?:खसरा\s*(?:नं\.?|संख्या|नंबर)|गाटा\s*(?:नं\.?|संख्या)|Khasra\s*(?:No\.?|Num(?:ber)?)|Gata\s*(?:No\.?|Num(?:ber)?))[:\s\-]*([0-9\/\-]+[a-zA-Z]?)"
    },
    "khata_number": {
        "standard_name": "khata_number",
        "display_name_en": "Khata Number / Khatauni",
        "display_name_hi": "खाता संख्या / खतौनी नं.",
        "aliases": [
            "खाता संख्या", "खाता नं.", "खतौनी संख्या", "खतौनी नं.", "खाता नंबर", "Khata No.",
            "Khata Number", "Khatauni No.", "Khatauni Number", "Khewat No.", "Account No."
        ],
        "regex": r"(?:खाता\s*(?:नं\.?|संख्या|नंबर)|खतौनी\s*(?:नं\.?|संख्या)|Khata\s*(?:No\.?|Num(?:ber)?)|Khatauni\s*(?:No\.?|Num(?:ber)?))[:\s\-]*([0-9\/\-]+)"
    },
    "survey_number": {
        "standard_name": "survey_number",
        "display_name_en": "Survey Number",
        "display_name_hi": "सर्वेक्षण संख्या",
        "aliases": [
            "सर्वे संख्या", "सर्वेक्षण संख्या", "सर्वे नं.", "Survey No.", "Survey Number", "Cadastral Survey No."
        ],
        "regex": r"(?:सर्वे\s*(?:नं\.?|संख्या)|Survey\s*(?:No\.?|Num(?:ber)?))[:\s\-]*([0-9\/\-]+)"
    },
    "area": {
        "standard_name": "area",
        "display_name_en": "Area / Extent",
        "display_name_hi": "रकबा / क्षेत्रफल",
        "aliases": [
            "रकबा", "क्षेत्रफल", "रकबा (हेक्टेयर)", "रकबा (बीघा)", "Area", "Total Area", "Extent", "Rakba"
        ],
        "regex": r"(?:रकबा|क्षेत्रफल|Area|Extent)[:\s\-]*([0-9]+(?:\.[0-9]+)?)"
    },
    "area_unit": {
        "standard_name": "area_unit",
        "display_name_en": "Area Unit",
        "display_name_hi": "माप की इकाई",
        "aliases": [
            "इकाई", "हेक्टेयर", "बीघा", "एकड़", "बिस्वा", "वर्ग मीटर", "Hectare", "Acre", "Bigha", "Biswa", "Sq. Meter"
        ],
        "regex": r"(हेक्टेयर|बीघा|एकड़|बिस्वा|वर्ग\s*मीटर|hectare|acre|bigha|biswa|sq\.?\s*meters?)"
    },
    "land_classification": {
        "standard_name": "land_classification",
        "display_name_en": "Land Classification",
        "display_name_hi": "भूमि का प्रकार / श्रेणी",
        "aliases": [
            "भूमि श्रेणी", "भूमि का प्रकार", "श्रेणी", "किस्म जमीन", "Land Type", "Land Classification", "Category"
        ],
        "regex": r"(?:भूमि\s*(?:श्रेणी|का\s*प्रकार)|किस्म\s*जमीन|Land\s*(?:Classification|Type))[:\s\-]+([^\n\r,]+)"
    },
    "mutation_number": {
        "standard_name": "mutation_number",
        "display_name_en": "Mutation Number",
        "display_name_hi": "दाखिल-खारिज / नामांतरण संख्या",
        "aliases": [
            "दाखिल खारिज संख्या", "नामांतरण क्रमांक", "नामांतरण सं.", "दाखिल खारिज नं.", "Mutation No.", "Mutation Number", "Fard No."
        ],
        "regex": r"(?:दाखिल[\s\-]खारिज\s*(?:संख्या|नं\.?)|नामांतरण\s*(?:क्रमांक|संख्या|सं\.?)|Mutation\s*(?:No\.?|Num(?:ber)?))[:\s\-]*([0-9a-zA-Z\/\-]+)"
    },
    "registration_number": {
        "standard_name": "registration_number",
        "display_name_en": "Registration Number",
        "display_name_hi": "पंजीकरण संख्या",
        "aliases": [
            "पंजीकरण संख्या", "दस्तावेज़ संख्या", "रजिस्ट्री क्रमांक", "Registration No.", "Deed No.", "Doc No."
        ],
        "regex": r"(?:पंजीकरण\s*(?:संख्या|नं\.?)|रजिस्ट्री\s*(?:क्रमांक|नं\.?)|Registration\s*(?:No\.?|Num(?:ber)?))[:\s\-]*([0-9a-zA-Z\/\-]+)"
    },
    "village": {
        "standard_name": "village",
        "display_name_en": "Village / Mouza",
        "display_name_hi": "ग्राम / मौजा",
        "aliases": [
            "ग्राम", "गाँव", "मौजा", "Village", "Mouza", "Gram"
        ],
        "regex": r"(?:ग्राम|गाँव|मौजा|Village|Mouza)[:\s\-]+([^\n\r,]+)"
    },
    "tehsil": {
        "standard_name": "tehsil",
        "display_name_en": "Tehsil / Taluka",
        "display_name_hi": "तहसील / तालुका",
        "aliases": [
            "तहसील", "तालुका", "अंचल", "Tehsil", "Taluk", "Taluka", "Circle", "Anchal"
        ],
        "regex": r"(?:तहसील|तालुका|अंचल|Tehsil|Taluk|Taluka)[:\s\-]+([^\n\r,]+)"
    },
    "district": {
        "standard_name": "district",
        "display_name_en": "District",
        "display_name_hi": "जनपद / जिला",
        "aliases": [
            "जनपद", "जिला", "District", "Zila", "Distt."
        ],
        "regex": r"(?:जनपद|जिला|District|Zila|Distt\.?)[:\s\-]+([^\n\r,]+)"
    },
    "state": {
        "standard_name": "state",
        "display_name_en": "State",
        "display_name_hi": "राज्य / प्रदेश",
        "aliases": [
            "राज्य", "प्रदेश", "State"
        ],
        "regex": r"(?:राज्य|प्रदेश|State)[:\s\-]+([^\n\r,]+)"
    }
}

# State-Specific Custom Mappings (UP, MP, Bihar, Maharashtra, Rajasthan, Punjab, Karnataka)
STATE_TERMINOLOGY_OVERLAYS = {
    "Uttar Pradesh": {
        "khasra_number": ["गाटा संख्या", "खसरा संख्या", "खसरा नं."],
        "khata_number": ["खाता संख्या", "खतौनी संख्या"],
        "area_unit": "hectare"
    },
    "Madhya Pradesh": {
        "khasra_number": ["खसरा क्रमांक", "खसरा नंबर"],
        "khata_number": ["खाता क्रमांक", "ऋण पुस्तिका संख्या"],
        "area_unit": "hectare"
    },
    "Bihar": {
        "khasra_number": ["खेसरा संख्या", "प्लॉट नंबर"],
        "khata_number": ["खाता संख्या", "जमाबंदी संख्या"],
        "area_unit": "acre"
    },
    "Maharashtra": {
        "khasra_number": ["गट क्रमांक", "सर्व्हे नंबर"],
        "khata_number": ["खाते क्रमांक", "7/12 उतारा"],
        "area_unit": "hectare"
    },
    "Rajasthan": {
        "khasra_number": ["खसरा नंबर", "जमाबंदी खसरा"],
        "khata_number": ["खेवट संख्या", "खाता संख्या"],
        "area_unit": "bigha"
    }
}

def map_alias_to_standard_field(term: str, state: Optional[str] = None) -> Optional[str]:
    """Finds standard field key from any regional / Hindi / English alias."""
    term_clean = term.strip().lower()
    
    # Check general dictionary
    for field_key, field_data in TERMINOLOGY_DICTIONARY.items():
        for alias in field_data["aliases"]:
            if alias.lower() in term_clean or term_clean in alias.lower():
                return field_key
    return None

def normalize_area_unit(unit_str: str) -> str:
    """Normalizes Hindi and regional unit text to standard unit code."""
    unit_str = unit_str.strip().lower()
    if any(u in unit_str for u in ["हेक्टेयर", "hectare", "हे०", "ha"]):
        return "hectare"
    elif any(u in unit_str for u in ["एकड़", "acre", "ac"]):
        return "acre"
    elif any(u in unit_str for u in ["बीघा", "bigha"]):
        return "bigha"
    elif any(u in unit_str for u in ["बिस्वा", "biswa"]):
        return "biswa"
    elif any(u in unit_str for u in ["वर्ग मीटर", "sq", "meter", "sqm"]):
        return "sq_meter"
    return "hectare"
