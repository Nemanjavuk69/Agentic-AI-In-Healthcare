import secrets
import urllib.request
import json
import chromadb
from sentence_transformers import SentenceTransformer
import logging
import os
import math
import random
import re
import html

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

os.environ["TQDM_DISABLE"] = "1"
logging.getLogger().setLevel(logging.WARNING)

# ── Mitigation: read URL and API key from environment variables ──────────────
OLLAMA_URL   = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_TOKEN = os.environ.get("OLLAMA_API_KEY", "")          # empty = no token

VAULT_FILE = "pii_vault.json"

# =========================
# Shared model and DB — loaded once, used by all agents
# =========================

print("Loading embedding model...")
embedding_model = SentenceTransformer("intfloat/multilingual-e5-large")
print("Model loaded.")

chroma_client = chromadb.PersistentClient(path="./dept_db")
collection = chroma_client.get_collection("dept_guidelines")
print("Connected to DEPT vector database.\n")





# =========================
# Core LLM call
# =========================

def call_llm(system_prompt: str, user_prompt: str,
             analyzer=None, anonymizer=None) -> str:

    payload = json.dumps({
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "stream": False
    }).encode("utf-8")

    # ── Mitigation 1: include Bearer token if one is configured ─────────────
    headers = {"Content-Type": "application/json"}
    if OLLAMA_TOKEN:
        headers["Authorization"] = f"Bearer {OLLAMA_TOKEN}"

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers=headers
    )

    with urllib.request.urlopen(req) as response:
        raw = json.loads(response.read())["message"]["content"]

    # ── Mitigation 2: sanitize LLM output before returning it ───────────────
    if analyzer and anonymizer:
        raw = anonymize_text(raw, analyzer=analyzer, anonymizer=anonymizer)

    return raw


# =========================
# RAG Retrieval
# Looks up the most relevant DEPT guideline chunks for the symptoms
# =========================

def add_gaussian_noise(vector, sigma: float = 0.01) -> list:
    """
    Adds small Gaussian noise independently to each embedding dimension.
    This reduces direct embedding invertibility while preserving most retrieval utility.
    """
    return [x + random.gauss(0, sigma) for x in vector]


def l2_normalize(vector: list) -> list:
    """
    Re-normalizes the perturbed embedding so cosine-similarity retrieval remains stable.
    """
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def retrieve_dept_context(user_input: str, n_results: int = 3, sigma: float = 0.005) -> str:
    """
    Looks up the most relevant DEPT guideline chunks for the symptoms.

    Mitigation:
    - embeds the query text
    - adds bounded Gaussian noise to reduce embedding invertibility
    - re-normalizes the vector before Chroma retrieval
    """
    query_vector = embedding_model.encode([user_input]).tolist()[0]

    # Mitigation: perturb the query embedding before sending to ChromaDB
    query_vector = add_gaussian_noise(query_vector, sigma=sigma)
    query_vector = l2_normalize(query_vector)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        include=["documents", "metadatas"]
    )

    context_parts = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        card = meta.get("card_name", "Unknown")
        context_parts.append(f"[DEPT Card: {card}]\n{doc}")

    return "\n\n---\n\n".join(context_parts)



def create_cpr_recognizer():
    """
    Creates a custom recognizer for Danish CPR numbers.
    """

    cpr_pattern = Pattern(
        name="danish_cpr_pattern",
        regex=r"\b\d{6}-?\d{4}\b",
        score=0.85
    )

    recognizer = PatternRecognizer(
        supported_entity="DANISH_CPR",
        patterns=[cpr_pattern],
        supported_language="en"
    )

    return recognizer


def anonymize_text(text: str, language: str = "en", analyzer=None, anonymizer=None) -> str:
    """
    Detects and anonymizes CPR numbers + other entities.
    """

    if not text:
        return text
    

    results = analyzer.analyze(
        text=text,
        entities=[
            "PERSON",
            "PHONE_NUMBER",
            "EMAIL_ADDRESS",
            "DANISH_CPR"
        ],
        language=language
    )

    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results
    )




    return anonymized_result.text


def tokenize_patient(cpr: str, name: str) -> str:
    """
    Creates a pseudonymized token for the patient and stores PII in an isolated vault.
    If the CPR already exists, it returns the existing token.
    """
    if os.path.exists(VAULT_FILE):
        with open(VAULT_FILE, "r", encoding="utf-8") as f:
            vault = json.load(f)
    else:
        vault = {}

    # Checking if we already have a token for this CPR
    for token, pii_data in vault.items():
        if pii_data["cpr"] == cpr:
            return token

    # Generate a new secure, synthetic ID
    new_token = f"P-{secrets.token_hex(3).upper()}"
    
    # Store the real PII mapped to the token
    vault[new_token] = {"cpr": cpr, "name": name}
    
    #Save the vault
    with open(VAULT_FILE, "w", encoding="utf-8") as f:
        json.dump(vault, f, indent=2, ensure_ascii=False)
        
    return new_token

def setup_analyzer_and_anonymizer():
    print("Loading Presidio engines...")
    analyzer = AnalyzerEngine()
    anonymizer = AnonymizerEngine()
    analyzer.registry.add_recognizer(create_cpr_recognizer())
    print("Presidio loaded.")
    return analyzer, anonymizer








# =========================
# Input Sanitization
# =========================

def sanitize_cpr(cpr: str) -> str:
    """Ensure CPR is exactly 10 digits with an optional hyphen."""
    cpr = cpr.strip()
    if not re.fullmatch(r"\d{6}-?\d{4}", cpr):
        raise ValueError("Invalid CPR format. Must be DDMMYY-XXXX.")
    return cpr

def sanitize_name(name: str) -> str:
    """Allow-list for names to prevent injection via structural fields."""
    name = name.strip()
    # Allow letters (incl. Danish), spaces, hyphens, and apostrophes. Max 100 chars.
    if not re.fullmatch(r"[A-Za-zæøåÆØÅ \-']{2,100}", name):
        raise ValueError("Invalid name format or length.")
    return html.escape(name)

def sanitize_age(age_str: str) -> int:
    """Strict integer boundary check."""
    try:
        age = int(age_str.strip())
    except ValueError:
        raise ValueError("Age must be a valid integer.")
    
    if age < 0 or age > 120:
        raise ValueError("Age out of reasonable bounds (0-120).")
    
    return age

def sanitize_postal_code(postal: str) -> str:
    """Danish postal codes must be exactly 4 digits."""
    postal = postal.strip()
    if not re.fullmatch(r"\d{4}", postal):
        raise ValueError("Invalid postal code format. Must be 4 digits.")
    return postal

def sanitize_free_text(text: str, max_length: int = 1000) -> str:
    """
    Sanitizes unstructured input (symptoms, chat).
    Mitigates buffer overflow / excessive token usage and strips control characters.
    """
    # Enforce strict length limit to protect context window
    text = text.strip()[:max_length]
    
    # Strip unprintable control characters (except newline \n and tab \t) 
    # to prevent terminal manipulation or LLM parser breakage.
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    
    return text