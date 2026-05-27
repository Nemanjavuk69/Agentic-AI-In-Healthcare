"""
vault_encryption.py — Fernet encryption for pii_vault.enc
===========================================================
Provides functions to encrypt/decrypt the sensitive vault file.
"""

from cryptography.fernet import Fernet
import os
import json
from pathlib import Path


def generate_key() -> bytes:
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key()


def save_key(key: bytes, key_file: str = ".vault.key"):
    """Save the encryption key to a file (must be protected!)."""
    with open(key_file, "wb") as f:
        f.write(key)
    # Restrict permissions to owner only (Unix-like systems)
    os.chmod(key_file, 0o600)


def load_key(key_file: str = ".vault.key") -> bytes:
    """Load the encryption key from file."""
    if not os.path.exists(key_file):
        raise FileNotFoundError(
            f"Key file '{key_file}' not found. Generate one with: "
            "python -c \"from vault_encryption import generate_key, save_key; "
            "save_key(generate_key())\""
        )
    with open(key_file, "rb") as f:
        return f.read()


def encrypt_vault(vault: dict, key: bytes) -> bytes:
    """
    Serialize vault dict to JSON and encrypt it.
    Returns encrypted bytes.
    """
    json_data = json.dumps(vault, indent=2, ensure_ascii=False).encode("utf-8")
    cipher = Fernet(key)
    encrypted = cipher.encrypt(json_data)
    return encrypted


def decrypt_vault(encrypted_data: bytes, key: bytes) -> dict:
    """
    Decrypt encrypted vault data and deserialize to dict.
    Returns the vault dict.
    """
    cipher = Fernet(key)
    json_data = cipher.decrypt(encrypted_data)
    vault = json.loads(json_data.decode("utf-8"))
    return vault


def load_vault(vault_file: str = "pii_vault.enc", key_file: str = ".vault.key") -> dict:
    """
    Load and decrypt the vault from disk.
    Returns {} if vault doesn't exist.
    """
    if not Path(vault_file).exists():
        return {}
    
    key = load_key(key_file)
    
    with open(vault_file, "rb") as f:
        encrypted_data = f.read()
    
    try:
        return decrypt_vault(encrypted_data, key)
    except Exception as e:
        raise ValueError(f"Failed to decrypt vault: {e}")


def save_vault(vault: dict, vault_file: str = "pii_vault.enc", key_file: str = ".vault.key"):
    """
    Encrypt and save the vault to disk.
    """
    key = load_key(key_file)
    encrypted_data = encrypt_vault(vault, key)
    
    with open(vault_file, "wb") as f:
        f.write(encrypted_data)
