import urllib.request
import json
import chromadb
from sentence_transformers import SentenceTransformer
import logging
import os


os.environ["TQDM_DISABLE"] = "1"
logging.getLogger().setLevel(logging.WARNING)

OLLAMA_URL = "http://localhost:11434/api/chat"

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
        "model": "qwen2.5:7b",
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
