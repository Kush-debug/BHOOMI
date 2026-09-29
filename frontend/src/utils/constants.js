export const DOCUMENT_TYPES = [
  { value: 'khasra_b1', label: 'खसरा प्रपत्र बी-1 (Khasra B1)', desc: 'Field-wise land parcel register' },
  { value: 'khatauni', label: 'उद्धरण खतौनी (Khatauni / ROR)', desc: 'Record of Rights by landholder account' },
  { value: 'mutation_fard', label: 'दाखिल खारिज पंजी (Mutation Fard)', desc: 'Transfer of title & inheritance order' },
  { value: 'cadastral_naksha', label: 'ग्राम भू-नक्शा (Cadastral Map)', desc: 'Village parcel map / field geometry' },
  { value: 'sale_deed', label: 'बैनामा / रजिस्ट्री (Sale Deed)', desc: 'Registered property deed' },
  { value: 'patta', label: 'भूमि आवंटन पट्टा (Land Patta)', desc: 'Government land allotment certificate' }
];

export const STATES = [
  "Uttar Pradesh", "Madhya Pradesh", "Bihar", "Maharashtra", "Rajasthan", "Punjab", "Karnataka"
];

export const DISTRICTS_MAP = {
  "Uttar Pradesh": ["Kanpur Nagar", "Varanasi", "Lucknow", "Prayagraj", "Gorakhpur"],
  "Madhya Pradesh": ["Indore", "Bhopal", "Ujjain", "Jabalpur", "Gwalior"],
  "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga"],
  "Maharashtra": ["Pune", "Nagpur", "Nashik", "Aurangabad", "Thane"],
  "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Udaipur"]
};

export const TEHSILS_MAP = {
  "Kanpur Nagar": ["Bilhaur", "Ghatampur", "Sadar", "Narwal"],
  "Varanasi": ["Sadar", "Pindra", "Raja Talab"],
  "Indore": ["Sanwer", "Depalpur", "Mhow", "Indore"],
  "Patna": ["Danapur", "Patna Sadar", "Barh", "Masaurhi"],
  "Pune": ["Haveli", "Pune City", "Baramati", "Shirur"],
  "Jaipur": ["Sanganer", "Amber", "Chaksu", "Kotputli"]
};

export const VILLAGES_MAP = {
  "Bilhaur": ["Bilhaur Dehat", "Makanpur", "Araul", "Chaubepur", "Radhan"],
  "Ghatampur": ["Bhitargaon", "Patara", "Ghatampur Khas"],
  "Sadar": ["Shivpur", "Lohta", "Manduadih", "Ramnagar"],
  "Sanwer": ["Chandrawatiganj", "Ajnod", "Kshipra", "Dharampuri"],
  "Danapur": ["Khagaul", "Maner", "Shahpur", "Dinapur"],
  "Haveli": ["Wagholi", "Hadapsar", "Loni Kalbhor", "Uruli Kanchan"],
  "Sanganer": ["Bagru", "Vatika", "Muhana", "Goner"]
};

export const ROLE_PRESETS = [
  { username: 'verification_officer', role: 'verification_officer', name: 'Shri Vinod Pathak (Verification Officer)', dept: 'Land Digitization Cell' },
  { username: 'tehsil_officer', role: 'tehsil_officer', name: 'Smt. Priyanka Tiwari (Tehsildar)', dept: 'Tehsil Bilhaur' },
  { username: 'district_officer', role: 'district_officer', name: 'Shri R. K. Sharma (District Collector)', dept: 'Kanpur Nagar Revenue' },
  { username: 'admin', role: 'admin', name: 'Dr. Alok Verma (State Director)', dept: 'Directorate of Land Records' },
  { username: 'viewer', role: 'viewer', name: 'Public / Citizen Viewer', dept: 'Public Portal' }
];
