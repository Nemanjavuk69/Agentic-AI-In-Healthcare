import secrets
import urllib.request
import json
import chromadb
from sentence_transformers import SentenceTransformer
import logging
import os


from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

os.environ["TQDM_DISABLE"] = "1"
logging.getLogger().setLevel(logging.WARNING)

OLLAMA_URL = "http://localhost:11434/api/chat"
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

def call_llm(system_prompt: str, user_prompt: str) -> str:
    payload = json.dumps({
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ],
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())["message"]["content"]


# =========================
# RAG Retrieval
# Looks up the most relevant DEPT guideline chunks for the symptoms
# =========================

def retrieve_dept_context(user_input: str, n_results: int = 3) -> str:
    query_vector = embedding_model.encode([user_input]).tolist()[0]

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


def sanitize_text(text: str, language: str = "en", analyzer=None, anonymizer=None) -> str:
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


