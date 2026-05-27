import json
import os
from cryptography.fernet import Fernet

KEY_FILE = ".vault.key"
VAULT_FILE = "pii_vault.enc"
PLAINTEXT_INPUT_FILE = "pii_vault_plain.json"

def load_key() -> bytes:
    if not os.path.exists(KEY_FILE):
        raise FileNotFoundError(f"Key file not found: {KEY_FILE}")
    with open(KEY_FILE, "rb") as f:
        return f.read().strip()

def encrypt_json_file(input_file: str, output_file: str) -> None:
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Plaintext input file not found: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        vault = json.load(f)

    plaintext = json.dumps(vault, indent=2, ensure_ascii=False).encode("utf-8")

    key = load_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext)

    with open(output_file, "wb") as f:
        f.write(encrypted)

    os.chmod(output_file, 0o600)

def main():
    encrypt_json_file(PLAINTEXT_INPUT_FILE, VAULT_FILE)
    print(f"Encrypted {PLAINTEXT_INPUT_FILE} -> {VAULT_FILE}")

if __name__ == "__main__":
    main()