"""
migrate_patients.py — Migrate old patient_db records to the new tokenized format
=================================================================================
Old format (P001, P002, P003):
  - patient_id is a plain string e.g. "P001"
  - real name stored directly in patient_db JSON
  - no vault entry

New format (P-6290BB, P-506206):
  - patient_id is a hex token e.g. "P-6290BB"
  - name is "" in patient_db
  - real name + CPR stored in pii_vault.json

What this script does for each old-format patient:
  1. Generates a new secure hex token
  2. Generates a fake but plausible Danish CPR (DDMMYY-XXXX)
  3. Writes real name + CPR to pii_vault.json
  4. Writes updated patient record (blanked name, new token) to patient_db/
  5. Deletes the old patient file

HOW TO RUN:
    python migrate_patients.py

    Dry run (preview only, no changes):
    python migrate_patients.py --dry-run
"""

import argparse
import json
import os
import re
import random
import secrets
from datetime import datetime
from pathlib import Path

PATIENT_DB_DIR = os.path.join(os.path.dirname(__file__), "patient_db")
VAULT_FILE     = os.path.join(os.path.dirname(__file__), "pii_vault.json")

# Matches old-format IDs: P001, P002, P003 etc. — NOT the new hex tokens
OLD_ID_PATTERN = re.compile(r"^P\d+$")


def is_old_format(patient: dict) -> bool:
    pid = patient.get("patient_id", "")
    return bool(OLD_ID_PATTERN.match(pid))


def generate_token() -> str:
    return f"P-{secrets.token_hex(3).upper()}"


def generate_fake_cpr(age: int, gender: str) -> str:
    """
    Generate a plausible fake Danish CPR (DDMMYY-XXXX).
    - Birth date derived from age (random day/month)
    - Last digit odd = male, even = female
    """
    birth_year  = datetime.now().year - age
    birth_month = random.randint(1, 12)
    days_in_month = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    birth_day   = random.randint(1, days_in_month[birth_month])

    dd = str(birth_day).zfill(2)
    mm = str(birth_month).zfill(2)
    yy = str(birth_year)[-2:]

    mid = random.randint(0, 999)
    if gender.lower() in ("male", "m", "mand"):
        gender_digit = random.choice([1, 3, 5, 7, 9])
    else:
        gender_digit = random.choice([0, 2, 4, 6, 8])

    seq = f"{str(mid).zfill(3)}{gender_digit}"
    return f"{dd}{mm}{yy}-{seq}"


def load_vault() -> dict:
    if Path(VAULT_FILE).exists():
        with open(VAULT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_vault(vault: dict):
    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        json.dump(vault, f, indent=2, ensure_ascii=False)


def migrate(dry_run: bool = False):
    vault = load_vault()

    files = [f for f in os.listdir(PATIENT_DB_DIR) if f.endswith(".json")]
    old_files = []

    for fname in files:
        path = os.path.join(PATIENT_DB_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            patient = json.load(f)
        if is_old_format(patient):
            old_files.append((fname, path, patient))

    if not old_files:
        print("No old-format patients found. Nothing to migrate.")
        return

    print(f"Found {len(old_files)} old-format patient(s) to migrate:\n")

    migrated = []

    for fname, path, patient in old_files:
        old_id    = patient["patient_id"]
        real_name = patient.get("name", "")
        age       = patient.get("age") or 30
        gender    = patient.get("gender", "male")

        # Generate unique token
        token = generate_token()
        while token in vault:
            token = generate_token()

        # Generate fake CPR based on age and gender
        cpr = generate_fake_cpr(age, gender)

        vault_entry = {
            "cpr":  cpr,
            "name": real_name,
        }

        # Updated patient record: new token, name blanked
        new_patient = {k: v for k, v in patient.items()}
        new_patient["patient_id"] = token
        new_patient["name"]       = ""

        new_fname = f"{token}.json"
        new_path  = os.path.join(PATIENT_DB_DIR, new_fname)

        print(f"  {old_id} ({real_name or 'no name'})")
        print(f"    → token : {token}")
        print(f"    → cpr   : {cpr}")
        print(f"    → file  : {fname} → {new_fname}")
        print()

        if not dry_run:
            with open(new_path, "w", encoding="utf-8") as f:
                json.dump(new_patient, f, indent=2, ensure_ascii=False)
            vault[token] = vault_entry
            os.remove(path)

        migrated.append((old_id, token))

    if not dry_run:
        save_vault(vault)
        print(f"Migration complete. {len(migrated)} patient(s) migrated.")
        print(f"Vault updated: {VAULT_FILE}")
    else:
        print("Dry run complete — no files were changed.")
        print("Run without --dry-run to apply.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate old patient records to tokenized format.")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing anything")
    args = parser.parse_args()

    migrate(dry_run=args.dry_run)