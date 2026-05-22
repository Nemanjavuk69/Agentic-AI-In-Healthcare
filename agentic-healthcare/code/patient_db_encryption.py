# patient_db_encryption.py — Patient Database Encryption (NEW MODULE)
from cryptography.fernet import Fernet
import json
from pathlib import Path
from vault_encryption import load_key, encrypt_vault, decrypt_vault

PATIENT_DB_FILE = "patient_db.enc"
PATIENT_DB_KEY_FILE = ".patient_db.key"

# In-memory cache for the entire patient database
_PATIENT_DB_CACHE = None

def load_patient_db(db_file: str = PATIENT_DB_FILE, key_file: str = PATIENT_DB_KEY_FILE) -> dict:
    """Load and decrypt the entire patient database."""
    if not Path(db_file).exists():
        return {}
    
    key = load_key(key_file)
    with open(db_file, "rb") as f:
        encrypted_data = f.read()
    
    try:
        return decrypt_vault(encrypted_data, key)
    except Exception as e:
        raise ValueError(f"Failed to decrypt patient database: {e}")


def save_patient_db(patient_db: dict, db_file: str = PATIENT_DB_FILE, key_file: str = PATIENT_DB_KEY_FILE):
    """Encrypt and save the entire patient database."""
    key = load_key(key_file)
    encrypted_data = encrypt_vault(patient_db, key)
    with open(db_file, "wb") as f:
        f.write(encrypted_data)


def get_patient_db_cache() -> dict:
    """Get in-memory patient database cache (loaded once at startup)."""
    global _PATIENT_DB_CACHE
    if _PATIENT_DB_CACHE is None:
        _PATIENT_DB_CACHE = load_patient_db()
    return _PATIENT_DB_CACHE


def update_patient_in_cache(patient_id: str, patient_data: dict):
    """Update a single patient in cache and persist to disk."""
    db = get_patient_db_cache()
    db[patient_id] = patient_data
    save_patient_db(db)


def clear_cache():
    """Clear in-memory cache (for testing)."""
    global _PATIENT_DB_CACHE
    _PATIENT_DB_CACHE = None