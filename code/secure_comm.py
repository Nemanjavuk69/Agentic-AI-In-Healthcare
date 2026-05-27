import hmac
import base64
import hashlib
import json
import time
import uuid
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from typing import Dict, Any, Iterable


# Sender-specific secrets used for HMAC signatures.
# In production, these would not be hardcoded. They would come from a secret
# manager or be replaced by workload identity + mTLS.
AGENT_SECRETS = {
    "agent1": b"agent1-secret",
    "agent2": b"agent2-secret",
    "agent3": b"agent3-secret",
}

# Define which agents can communicate and for what actions
AUTHORIZED_COMMUNICATIONS = {
    ("agent1", "agent2", "emergency_routing"),
    ("agent1", "agent3", "follow_up"),
}

# For the evaluation script we use deterministic dev keys so the demo runs
# without requiring environment setup. Replace with env-based keys in real use.
DEV_FERNET_KEYS = [
    base64.urlsafe_b64encode(hashlib.sha256(b"new-demo-key").digest()),
    base64.urlsafe_b64encode(hashlib.sha256(b"old-demo-key").digest()),
]

# Generate Fernet keys for encryption
#FERNET_KEYS = [
#    Fernet.generate_key(),
#    Fernet.generate_key(),
#]

#cipher = MultiFernet([Fernet(key) for key in FERNET_KEYS])

# ===============================================
# helper function
# ===============================================


# Canonical JSON encoding for consistent signing
def canonical_json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


# ================================================
# MuliFernet encryption with key rotation
# ================================================

def get_cipher(keys: Iterable[bytes] | None = None) -> MultiFernet:
    key_list = list(keys or DEV_FERNET_KEYS)
    return MultiFernet([Fernet(k) for k in key_list])


def encrypt_message(message: Dict[str, Any], cipher: MultiFernet | None = None) -> str:
    cipher = cipher or get_cipher()
    return cipher.encrypt(canonical_json(message)).decode("utf-8")


def decrypt_message(token: str, cipher: MultiFernet | None = None) -> Dict[str, Any]:
    cipher = cipher or get_cipher()
    plaintext = cipher.decrypt(token.encode("utf-8"))
    return json.loads(plaintext.decode("utf-8"))

# ================================================
# Message signing and verification
# ================================================

# Sign a message using HMAC with the sender's secret
def sign_message(sender: str, message_without_signature: Dict[str, Any]) -> str:
    if sender not in AGENT_SECRETS:
        raise PermissionError(f"Unknown sender: {sender}")
    return hmac.new(
        AGENT_SECRETS[sender],
        canonical_json(message_without_signature),
        hashlib.sha256
    ).hexdigest()


# Verify the signature of a received message
def verify_signature(message: Dict[str, Any]) -> bool:
    signature = message.get("signature")
    sender = message.get("sender")

    if sender not in AGENT_SECRETS or not signature:
        return False

    unsigned = dict(message)
    unsigned.pop("signature", None)

    expected = sign_message(sender, unsigned)
    return hmac.compare_digest(signature, expected)

# ================================================
# Policy-based communication control

# Check if the sender is authorized to communicate with the receiver for the given action
def is_authorised(sender, receiver, action):
    return (sender, receiver, action) in AUTHORIZED_COMMUNICATIONS


# Create a secure message with authorization, signing, and encryption
def create_secure_message(sender, receiver, action, payload, encrypt: bool = True):
    if not is_authorised(sender, receiver, action):
        print(f"Unauthorized communication attempt: {sender} -> {receiver} for action '{action}'")
        raise PermissionError("Unauthorised inter-agent communication")

    message = {
        "message_id": str(uuid.uuid4()),
        "timestamp": int(time.time()),
        "sender": sender,
        "receiver": receiver,
        "action": action,
        "payload": payload,
    }

    message["signature"] = sign_message(sender, message)

    if encrypt:
        return encrypt_message(message)

    return message

# Receive a secure message, verify authorization and signature, and return the payload
def receive_secure_message(expected_receiver, encrypted_message, encrypted: bool = True) -> Dict[str, Any]: 
    try:
        message = decrypt_message(encrypted_message) if encrypted else encrypted_message
    except InvalidToken as exc:
        raise PermissionError("Decryption failed: message is invalid or was modified") from exc

    if not isinstance(message, dict):
        raise PermissionError("Invalid message format")

    if message.get("receiver") != expected_receiver:
        raise PermissionError(
            f"Wrong receiver: expected {expected_receiver}, got {message.get('receiver')}"
        )

    if not verify_signature(message):
        raise PermissionError("Invalid HMAC signature: message may be forged or modified")

    sender = message["sender"]
    receiver = message["receiver"]
    action = message["action"]

    if not is_authorised(sender, receiver, action):
        raise PermissionError(
            f"Policy denied at receiver: {sender} -> {receiver} ({action})"
        )

    return message["payload"]
