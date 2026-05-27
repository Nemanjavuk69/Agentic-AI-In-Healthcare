import json
import random
import os
from pathlib import Path
from datetime import datetime

# ========================= CONFIG =========================
NUM_PATIENTS = 600                    # Change between 400-700
PATIENT_DB_DIR = Path("patients_db")
PATIENT_DB_DIR.mkdir(exist_ok=True)

# Realistic data pools

FIRST_NAMES_FEMALE= ["Ella", "Emma", "Frida", "Olivia", "Nora", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia", "Freja", "Clara", "Sofia", "Ida", "Liva", "Alma", "Laura", "Caroline", "Sara", "Mathilde", "Anna"]
FIRST_NAMES_MALE=["John", "Michael", "David", "James", "Robert", "William", "Thomas", "Daniel", "Matthew", "Joseph", "Christopher", "Andrew", "Joshua", "Anthony", "Mark", "Paul", "Steven", "Kevin", "Brian", "George"]
LAST_NAMES = ["Nielsen", "Jensen", "Hansen", "Pedersen", "Andersen", "Christensen", "Larsen", "Sørensen", "Rasmussen", "Petersen", "Jørgensen", "Madsen", "Kristensen", "Olsen", "Andreasen", "Mortensen", "Møller", "Jacobsen", "Frandsen", "Holm", "Mikkelsen", "Knudsen", "Høgh", "Vestergaard", "Carlsen"]
CHRONIC_DISEASES = ["Hypertension", "Type 2 Diabetes", "Asthma", "Cancer", "Arthritis", "Depression", "Migraine", "None"]
MEDICATIONS = ["Metformin", "Lisinopril", "Antiretrovirals", "Insulin", "Ventolin", "Paracetamol", "Sertraline", "None"]
ALLERGIES = ["Penicillin", "Nuts", "Dust", "None"]

def generate_patient(patient_id: int):

    gender = random.choices(
        ["female", "male", "other"],
        weights=[0.48, 0.48, 0.04],  # ~4% other
        k=1
    )[0]
    
        # Pick first name based on gender
    if gender == "female":
        first = random.choice(FIRST_NAMES_FEMALE)
    elif gender == "male":
        first = random.choice(FIRST_NAMES_MALE)
    else:  # "other"
        first = random.choice(FIRST_NAMES_FEMALE + FIRST_NAMES_MALE)

    last = random.choice(LAST_NAMES)

    postal_code = ["1000", "1050", "1100", "1150", "1200", "1250", "1300", "1350", "1400", "1450", "1500",
        "1550", "1600", "1650", "1700","2000", "2100", "2200", "2300", "2400","2500","2600", "2610", "2620", "2630","2700", 
        "2720", "2730", "2740","2800", "2820", "2830", "2840", "2850", "2860","2900"]
    
    return {
        "patient_id": f"P{patient_id:03d}",
        "name": f"{first} {last}",
        "age": random.randint(18, 85),
        "gender": gender,
        "postal_code": random.choice(postal_code),
        "chronic_diseases": random.sample(CHRONIC_DISEASES, k=random.randint(0, 3)),
        "medications": random.sample(MEDICATIONS, k=random.randint(0, 3)),
        "allergies": random.sample(ALLERGIES, k=random.randint(0, 2)),
        "hospital": "Aalborg University Hospital"
    }

def main():
    print(f"Generating {NUM_PATIENTS} synthetic patients...")
    
    for i in range(1, NUM_PATIENTS + 1):
        patient = generate_patient(i)
        filepath = PATIENT_DB_DIR / f"{patient['patient_id']}.json"
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(patient, f, indent=2, ensure_ascii=False)
        
        if i % 100 == 0:
            print(f"  → Generated {i}/{NUM_PATIENTS} patients")

    print(f"\n✅ Successfully generated {NUM_PATIENTS} synthetic patients in '{PATIENT_DB_DIR}' folder!")
    print(f"Total files: {len(list(PATIENT_DB_DIR.glob('*.json')))}")

if __name__ == "__main__":
    main()