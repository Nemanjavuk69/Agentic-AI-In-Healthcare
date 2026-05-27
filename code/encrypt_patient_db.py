#!/usr/bin/env python3
"""
encrypt_patient_db.py — Migrate plaintext patient_db/ to encrypted database
"""

import json
import os
import shutil
import argparse
from pathlib import Path

# Import what exists in patient_db_encryption
from patient_db_encryption import load_patient_db, save_patient_db, PATIENT_DB_KEY_FILE, PATIENT_DB_FILE
from vault_encryption import generate_key, save_key

PATIENT_DB_DIR = "patient_db"


def setup_keys_if_missing():
    """Generate encryption key if it doesn't exist."""
    if os.path.exists(PATIENT_DB_KEY_FILE):
        print(f"✓ Key already exists: {PATIENT_DB_KEY_FILE}")
        return
    
    print(f"🔑 Generating new encryption key: {PATIENT_DB_KEY_FILE}")
    key = generate_key()
    save_key(key, PATIENT_DB_KEY_FILE)
    print(f"✓ Key generated and saved")


def migrate_patient_db(dry_run=False, backup=False):
    """Migrate all plaintext patient JSON files to encrypted database."""
    
    # Ensure encryption key exists
    setup_keys_if_missing()
    
    # Find all patient JSON files
    if not os.path.isdir(PATIENT_DB_DIR):
        print(f"❌ Directory '{PATIENT_DB_DIR}' not found.")
        return
    
    patient_files = [f for f in os.listdir(PATIENT_DB_DIR) if f.endswith(".json")]
    
    if not patient_files:
        print(f"⚠️  No JSON files in '{PATIENT_DB_DIR}'. Nothing to migrate.")
        return
    
    print(f"\n📋 Found {len(patient_files)} patient file(s)")
    print("-" * 70)
    
    # Load all patients into single database
    patient_db = {}
    errors = []
    
    for fname in patient_files:
        path = os.path.join(PATIENT_DB_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                patient = json.load(f)
            
            patient_id = patient.get("patient_id")
            if not patient_id:
                errors.append(f"  ⚠️  {fname}: Missing 'patient_id'")
                continue
            
            patient_db[patient_id] = patient
            print(f"  ✓ {fname}")
        
        except Exception as e:
            errors.append(f"  ❌ {fname}: {e}")
    
    if errors:
        print("\n⚠️  Errors:")
        for error in errors:
            print(error)
    
    print(f"\n📦 Loaded {len(patient_db)} patients")
    
    if dry_run:
        print("[DRY RUN] Would save to: " + PATIENT_DB_FILE)
        print(f"[DRY RUN] File size: ~{len(json.dumps(patient_db))} bytes")
        return
    
    # Encrypt and save
    print(f"\n🔐 Encrypting...")
    save_patient_db(patient_db, PATIENT_DB_FILE, PATIENT_DB_KEY_FILE)
    
    # Backup if requested
    if backup:
        backup_dir = os.path.join(PATIENT_DB_DIR, ".backup")
        os.makedirs(backup_dir, exist_ok=True)
        for fname in patient_files:
            src = os.path.join(PATIENT_DB_DIR, fname)
            dst = os.path.join(backup_dir, fname)
            shutil.copy2(src, dst)
        print(f"✓ Backup: {backup_dir}")
    
    # Delete plaintext files
    print(f"\n🗑️  Removing plaintext files...")
    for fname in patient_files:
        os.remove(os.path.join(PATIENT_DB_DIR, fname))
        print(f"  ✓ Deleted {fname}")
    
    print("\n✅ MIGRATION COMPLETE")
    print(f"  Encrypted: {PATIENT_DB_FILE}")
    print(f"  Key: {PATIENT_DB_KEY_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", action="store_true")
    args = parser.parse_args()
    
    migrate_patient_db(dry_run=args.dry_run, backup=args.backup)