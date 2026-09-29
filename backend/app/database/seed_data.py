from sqlalchemy.orm import Session

from app.auth.jwt import get_password_hash
from app.config import settings
from app.models.gis import GISParcel
from app.models.location import Country, District, State, Tehsil, Village
from app.models.user import User
from app.models.validation import MasterLandRegistry, MasterLocation

# ALL 28 STATES AND 8 UNION TERRITORIES OF INDIA (36 TOTAL)
ALL_INDIAN_STATES_UTS = [
    # 28 States
    {"name": "Andhra Pradesh", "code": "AP", "type": "STATE"},
    {"name": "Arunachal Pradesh", "code": "AR", "type": "STATE"},
    {"name": "Assam", "code": "AS", "type": "STATE"},
    {"name": "Bihar", "code": "BR", "type": "STATE"},
    {"name": "Chhattisgarh", "code": "CG", "type": "STATE"},
    {"name": "Goa", "code": "GA", "type": "STATE"},
    {"name": "Gujarat", "code": "GJ", "type": "STATE"},
    {"name": "Haryana", "code": "HR", "type": "STATE"},
    {"name": "Himachal Pradesh", "code": "HP", "type": "STATE"},
    {"name": "Jharkhand", "code": "JH", "type": "STATE"},
    {"name": "Karnataka", "code": "KA", "type": "STATE"},
    {"name": "Kerala", "code": "KL", "type": "STATE"},
    {"name": "Madhya Pradesh", "code": "MP", "type": "STATE"},
    {"name": "Maharashtra", "code": "MH", "type": "STATE"},
    {"name": "Manipur", "code": "MN", "type": "STATE"},
    {"name": "Meghalaya", "code": "ML", "type": "STATE"},
    {"name": "Mizoram", "code": "MZ", "type": "STATE"},
    {"name": "Nagaland", "code": "NL", "type": "STATE"},
    {"name": "Odisha", "code": "OD", "type": "STATE"},
    {"name": "Punjab", "code": "PB", "type": "STATE"},
    {"name": "Rajasthan", "code": "RJ", "type": "STATE"},
    {"name": "Sikkim", "code": "SK", "type": "STATE"},
    {"name": "Tamil Nadu", "code": "TN", "type": "STATE"},
    {"name": "Telangana", "code": "TS", "type": "STATE"},
    {"name": "Tripura", "code": "TR", "type": "STATE"},
    {"name": "Uttar Pradesh", "code": "UP", "type": "STATE"},
    {"name": "Uttarakhand", "code": "UK", "type": "STATE"},
    {"name": "West Bengal", "code": "WB", "type": "STATE"},
    # 8 Union Territories
    {"name": "Andaman and Nicobar Islands", "code": "AN", "type": "UNION_TERRITORY"},
    {"name": "Chandigarh", "code": "CH", "type": "UNION_TERRITORY"},
    {"name": "Dadra and Nagar Haveli and Daman and Diu", "code": "DN", "type": "UNION_TERRITORY"},
    {"name": "Delhi", "code": "DL", "type": "UNION_TERRITORY"},
    {"name": "Jammu and Kashmir", "code": "JK", "type": "UNION_TERRITORY"},
    {"name": "Ladakh", "code": "LA", "type": "UNION_TERRITORY"},
    {"name": "Lakshadweep", "code": "LD", "type": "UNION_TERRITORY"},
    {"name": "Puducherry", "code": "PY", "type": "UNION_TERRITORY"}
]

# Detailed Hierarchy across Key Revenue Zones
DETAILED_LOCATIONS = {
    "Uttar Pradesh": {
        "Kanpur Nagar": {
            "Bilhaur": ["Bilhaur Dehat", "Makanpur", "Araul", "Chaubepur", "Radhan", "Kalyanpur"],
            "Ghatampur": ["Bhitargaon", "Patara", "Ghatampur Khas", "Rehupur"],
            "Sadar": ["Shivpur", "Lohta", "Manduadih", "Rawatpur"],
            "Narwal": ["Narwal Dehat", "Pali", "Chandel Nagar"]
        },
        "Varanasi": {
            "Sadar": ["Shivpur", "Lohta", "Manduadih", "Ramnagar"],
            "Pindra": ["Pindra Khas", "Phoolpur", "Sindhora"],
            "Raja Talab": ["Raja Talab", "Kachhwa Road", "Mirzamurad"]
        },
        "Lucknow": {
            "Bakshi Ka Talab": ["BKT Dehat", "Itaunja", "Kathwara"],
            "Sarojini Nagar": ["Amausi", "Banthra", "Rahimabad"],
            "Malihabad": ["Malihabad Khas", "Kasmandi", "Saspan"]
        },
        "Prayagraj": {
            "Phulpur": ["Phulpur Dehat", "Sahson", "Jhusi"],
            "Koraon": ["Koraon Khas", "Barokhar", "Ghurpur"]
        }
    },
    "Tamil Nadu": {
        "Coimbatore": {
            "Pollachi": ["Anamalai", "Zamin Uthukuli", "Kottur", "Somandurai"],
            "Coimbatore South": ["Perur", "Madukkarai", "Sundakkamuthur"],
            "Mettupalayam": ["Sirumugai", "Karamadai", "Nellithurai"]
        },
        "Chennai": {
            "Egmore": ["Egmore North", "Chetpet", "Kilpauk"],
            "Mylapore": ["Mylapore Central", "Mandaveli", "Alwarpet"],
            "Guindy": ["Guindy Industrial", "Saidapet", "Ekkattuthangal"]
        },
        "Madurai": {
            "Madurai North": ["Alanganallur", "Palamedu", "Othakadai"],
            "Melur": ["Melur Khas", "Kottampatti", "Vellalore"]
        }
    },
    "Karnataka": {
        "Bengaluru Rural": {
            "Nelamangala": ["Kasaba", "Doddabele", "Sompura", "Thyamagondlu"],
            "Devanahalli": ["Vijayapura", "Kundana", "Avathi"],
            "Hosakote": ["Jadigenahalli", "Nandagudi", "Sulibele"]
        },
        "Mysuru": {
            "Mysuru Taluk": ["Varuna", "Yelwal", "Jayapura"],
            "Nanjangud": ["Hullahalli", "Kowlande", "Hadinaru"]
        }
    },
    "Andhra Pradesh": {
        "Krishna": {
            "Machilipatnam": ["Bandar", "Chilakalapudi", "Guduru"],
            "Vijayawada Urban": ["Gunadala", "Patamata", "Bhavanipuram"]
        },
        "Guntur": {
            "Tenali": ["Tenali Rural", "Burripalem", "Kollipara"],
            "Mangalagiri": ["Nowlur", "Nidamarru", "Kuragallu"]
        }
    },
    "Madhya Pradesh": {
        "Indore": {
            "Sanwer": ["Chandrawatiganj", "Ajnod", "Kshipra", "Dharampuri"],
            "Depalpur": ["Betma", "Gautampura", "Machal"],
            "Mhow": ["Dr Ambedkar Nagar", "Harsola", "Hasalpur"]
        },
        "Bhopal": {
            "Huzur": ["Bairagarh", "Kolar", "Misrod"],
            "Berasia": ["Berasia Dehat", "Narsingarh Road", "Gunga"]
        }
    },
    "Bihar": {
        "Patna": {
            "Danapur": ["Khagaul", "Maner", "Shahpur", "Dinapur"],
            "Patna Sadar": ["Phulwari Sharif", "Fatwah", "Sampatchak"]
        },
        "Gaya": {
            "Bodh Gaya": ["Mastipur", "Teka Bigha", "Bakrour"],
            "Sherghati": ["Sherghati Khas", "Dobhi", "Barachatti"]
        }
    },
    "Maharashtra": {
        "Pune": {
            "Haveli": ["Wagholi", "Hadapsar", "Loni Kalbhor", "Uruli Kanchan"],
            "Baramati": ["Baramati Rural", "Malegaon", "Supi"]
        },
        "Nagpur": {
            "Nagpur Rural": ["Kamptee", "Hingna", "Wadi"],
            "Katol": ["Katol Dehat", "Narkhed", "Mowad"]
        }
    },
    "Rajasthan": {
        "Jaipur": {
            "Sanganer": ["Bagru", "Vatika", "Muhana", "Goner"],
            "Amber": ["Amer Khas", "Kukas", "Jalsu"]
        }
    },
    "Delhi": {
        "North West Delhi": {
            "Narela": ["Alipur", "Narela Rural", "Bakhtawarpur"],
            "Saraswati Vihar": ["Rohini", "Pitampura", "Shalimar Bagh"]
        }
    }
}

def seed_reference_data(db: Session) -> None:
    """Seed reference data only.

    WHAT CHANGED (ARCHITECTURE_AUDIT §4.5, §4.12)
    ---------------------------------------------
    This function used to insert five fully-formed "demo documents" complete with
    OCR text, extracted fields, per-field confidences and placeholder bounding
    boxes, plus a ValidationResult whose rule_name (MASTER_REGISTRY_AREA_MATCH)
    does not exist in validation_service — the flagship demo anomaly was a
    literal, not an engine output.

    Those inserts are gone. Documents now only ever enter the system through
    /documents/upload and are processed by the real pipeline. The demo corpus
    arrives in a later phase as actual PDF files that go through that same path.

    What is still seeded, because it is genuine reference data:
      - country / state / district / tehsil / village hierarchy
      - the mock master land registry used for cross-database validation
      - initial user accounts
      - synthetic GIS parcels, tagged SEED_SYNTHETIC (opt-in)
    """
    if db.query(Country).count() > 0:
        return

    print("🌱 Seeding Country and 36 Indian States & Union Territories Master Data...")
    country = Country(name="India", code="IN", is_active=True)
    db.add(country)
    db.flush()

    state_obj_map = {}
    for st_data in ALL_INDIAN_STATES_UTS:
        st = State(
            country_id=country.id,
            name=st_data["name"],
            code=st_data["code"],
            type=st_data["type"],
            is_active=True
        )
        db.add(st)
        db.flush()
        state_obj_map[st_data["name"]] = st

    # Seed Hierarchical Districts, Tehsils & Villages
    for state_name, districts in DETAILED_LOCATIONS.items():
        st_obj = state_obj_map.get(state_name)
        if not st_obj:
            continue
        for dist_name, tehsils in districts.items():
            dist = District(
                state_id=st_obj.id,
                name=dist_name,
                code=f"{st_obj.code}-{dist_name[:3].upper()}",
                is_active=True
            )
            db.add(dist)
            db.flush()

            for tehsil_name, villages in tehsils.items():
                teh = Tehsil(
                    district_id=dist.id,
                    name=tehsil_name,
                    code=f"{dist.code}-{tehsil_name[:3].upper()}",
                    is_active=True
                )
                db.add(teh)
                db.flush()

                for v_name in villages:
                    v = Village(
                        tehsil_id=teh.id,
                        name=v_name,
                        village_code=f"VIL-{teh.id}-{len(v_name)*17}",
                        pincode="209202" if "Kanpur" in dist_name else "642001",
                        is_active=True
                    )
                    db.add(v)
                    # Also add to legacy MasterLocation table for full backwards compatibility
                    legacy_loc = MasterLocation(
                        state=state_name,
                        district=dist_name,
                        tehsil=tehsil_name,
                        village=v_name,
                        pincode=v.pincode
                    )
                    db.add(legacy_loc)

    print("Seeding mock master land registry (cross-validation reference)...")
    # NOTE: this table stands in for an authoritative government registry that is
    # not available to this prototype. It is a MOCK. Nothing in the UI may present
    # a match against it as government verification.
    master_records = [
        {"state": "Uttar Pradesh", "district": "Kanpur Nagar", "tehsil": "Bilhaur", "village": "Bilhaur Dehat", "khasra": "456", "khata": "142", "owner": "राम प्रसाद", "father": "श्याम सुंदर", "area": 0.70, "unit": "hectare", "class": "Agricultural"},
        {"state": "Uttar Pradesh", "district": "Kanpur Nagar", "tehsil": "Bilhaur", "village": "Bilhaur Dehat", "khasra": "451", "khata": "120", "owner": "सुरेश कुमार", "father": "राधे मोहन", "area": 1.12, "unit": "hectare", "class": "Agricultural"},
        {"state": "Uttar Pradesh", "district": "Kanpur Nagar", "tehsil": "Bilhaur", "village": "Bilhaur Dehat", "khasra": "512", "khata": "88", "owner": "अनिता देवी", "father": "महेश कुमार", "area": 0.42, "unit": "hectare", "class": "Agricultural"},
        {"state": "Tamil Nadu", "district": "Coimbatore", "tehsil": "Pollachi", "village": "Anamalai", "khasra": "123/4", "khata": "842", "owner": "ராமசாமி", "father": "முருகன்", "area": 0.85, "unit": "hectare", "class": "Agricultural (Wet / நஞ்சை)"},
        {"state": "Andhra Pradesh", "district": "Krishna", "tehsil": "Machilipatnam", "village": "Bandar", "khasra": "88/2", "khata": "315", "owner": "వెంకటేశ్వర్లు", "father": "సత్యనారాయణ", "area": 1.25, "unit": "hectare", "class": "Agricultural (Wet / మాగాణి)"},
        {"state": "Karnataka", "district": "Bengaluru Rural", "tehsil": "Nelamangala", "village": "Kasaba", "khasra": "65/1", "khata": "220", "owner": "ಮಂಜುನಾಥ್", "father": "ಬಸವರಾಜ್", "area": 0.90, "unit": "hectare", "class": "Agricultural (Irrigated / ತರಿ)"},
        {"state": "Madhya Pradesh", "district": "Indore", "tehsil": "Sanwer", "village": "Chandrawatiganj", "khasra": "78", "khata": "45", "owner": "कमलेश पाटीदार", "father": "भगवान सिंह", "area": 2.45, "unit": "hectare", "class": "Agricultural"},
    ]
    for mr in master_records:
        db.add(MasterLandRegistry(
            state=mr["state"], district=mr["district"], tehsil=mr["tehsil"], village=mr["village"],
            khasra_number=mr["khasra"], khata_number=mr["khata"], owner_name=mr["owner"],
            father_name=mr["father"], area=mr["area"], area_unit=mr["unit"],
            land_classification=mr["class"],
        ))

    _seed_users(db)

    if settings.ENABLE_DEMO_SEED:
        _seed_demo_gis_parcels(db)

    db.commit()
    print("Reference data seeded. No documents were created: documents only enter "
          "the system through upload and real processing.")


def _seed_users(db: Session) -> None:
    """Create initial accounts.

    Outside development a password must be supplied via SEED_DEFAULT_PASSWORD;
    there are no built-in credentials.
    """
    if settings.is_development:
        passwords = {
            "superadmin": "superadmin123",
            "admin": "admin123",
            "district_officer": "officer123",
            "tehsil_officer": "officer123",
            "verification_officer": "officer123",
            "viewer": "viewer123",
        }
        print("Seeding development accounts (development environment only).")
    else:
        if not settings.SEED_DEFAULT_PASSWORD:
            print("SEED_DEFAULT_PASSWORD is not set; skipping user seeding. "
                  "Create the first administrator manually.")
            return
        passwords = {k: settings.SEED_DEFAULT_PASSWORD for k in
                     ["superadmin", "admin", "district_officer", "tehsil_officer",
                      "verification_officer", "viewer"]}

    specs = [
        ("superadmin", "superadmin@bhoomi.gov.in", "Dr. Rajeshwar Sharma (Director General of Land Records)", "super_admin", "Central Land Resources Authority", "Delhi", "New Delhi", "Central Delhi"),
        ("admin", "admin@up.bhoomi.gov.in", "Dr. Alok Verma (State Director)", "admin", "Directorate of Land Records", "Uttar Pradesh", "Lucknow", "Sadar"),
        ("district_officer", "dm.kanpur@up.gov.in", "Shri R. K. Sharma (District Magistrate / Collector)", "district_officer", "Kanpur Nagar Revenue Administration", "Uttar Pradesh", "Kanpur Nagar", "Sadar"),
        ("tehsil_officer", "tehsildar.bilhaur@up.gov.in", "Smt. Priyanka Tiwari (Tehsildar)", "tehsil_officer", "Tehsil Revenue Court", "Uttar Pradesh", "Kanpur Nagar", "Bilhaur"),
        ("verification_officer", "kanoongo.bilhaur@up.gov.in", "Shri Vinod Pathak (Senior Revenue Inspector)", "verification_officer", "Land Record Verification Cell", "Uttar Pradesh", "Kanpur Nagar", "Bilhaur"),
        ("viewer", "citizen.viewer@bhoomi.gov.in", "Public / Citizen User", "viewer", "Citizen Land Portal", "Uttar Pradesh", "Kanpur Nagar", "Bilhaur"),
    ]
    for username, email, full_name, role, dept, state, district, tehsil in specs:
        db.add(User(
            username=username, email=email,
            password_hash=get_password_hash(passwords[username]),
            full_name=full_name, role=role, department=dept,
            state=state, district=district, tehsil=tehsil,
        ))


def _seed_demo_gis_parcels(db: Session) -> None:
    """Synthetic cadastral geometry for UI development.

    Tagged SEED_SYNTHETIC. The API returns source_class with every feature so the
    map can label these as demo geometry rather than surveyed boundaries.
    """
    print("Seeding synthetic GIS parcels (tagged SEED_SYNTHETIC).")
    parcels = [
        {"khasra": "456", "khata": "142", "owner": "राम प्रसाद", "area": 0.70, "status": "mismatch",
         "poly": [[[80.0540, 26.8530], [80.0560, 26.8530], [80.0558, 26.8510], [80.0538, 26.8512], [80.0540, 26.8530]]], "cent": [80.0549, 26.8521]},
        {"khasra": "451", "khata": "120", "owner": "सुरेश कुमार", "area": 1.12, "status": "verified",
         "poly": [[[80.0560, 26.8530], [80.0585, 26.8532], [80.0582, 26.8508], [80.0558, 26.8510], [80.0560, 26.8530]]], "cent": [80.0571, 26.8520]},
        {"khasra": "512", "khata": "88", "owner": "अनिता देवी", "area": 0.42, "status": "pending",
         "poly": [[[80.0538, 26.8512], [80.0558, 26.8510], [80.0555, 26.8490], [80.0535, 26.8492], [80.0538, 26.8512]]], "cent": [80.0546, 26.8501]},
    ]
    for gp in parcels:
        db.add(GISParcel(
            khasra_number=gp["khasra"], khata_number=gp["khata"], owner_name=gp["owner"],
            area=gp["area"], area_unit="hectare", land_classification="Agricultural",
            state="Uttar Pradesh", district="Kanpur Nagar", tehsil="Bilhaur", village="Bilhaur Dehat",
            source_class="SEED_SYNTHETIC",
            geometry_geojson={"type": "Polygon", "coordinates": gp["poly"]},
            centroid_geojson={"type": "Point", "coordinates": gp["cent"]},
            verification_status=gp["status"],
        ))


# Backwards-compatible alias for existing callers/tests.
seed_all_data = seed_reference_data
