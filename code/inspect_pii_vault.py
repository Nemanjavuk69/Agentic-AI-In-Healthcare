import json
import os
from cryptography.fernet import Fernet, InvalidToken

KEY_FILE = ".vault.key"
VAULT_FILE = "pii_vault.enc"

def load_key() -> bytes:
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError(f"Key file not found: {KEY_FILE}")
    with open(KEY_FILE, "rb") as f:
        return f.read().strip()

def decrypt_vault() -> dict:
    if not os.path.exists(VAULT_FILE):
        raise FileNotFoundError(f"Vault file not found: {VAULT_FILE}")

    key = load_key()
    fernet = Fernet(key)

    with open(VAULT_FILE, "rb") as f:
        encrypted_data = f.read()

    try:
        decrypted_data = fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode("utf-8"))
    except InvalidToken:
        raise RuntimeError(
            "Could not decrypt vault. The file may still be plaintext JSON, "
            "corrupted, or encrypted with a different key."
        )

def main():
    vault = decrypt_vault()
    print(json.dumps(vault, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()