import json
import chromadb
from sentence_transformers import SentenceTransformer

def embed_chunks():
    # Load your chunks
    with open("dept_chunks.json", "r", encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Loaded {len(chunks)} chunks from dept_chunks.json")

    # Load the embedding model
    # This model handles Danish text well and is completely free
    print("Loading embedding model (first run downloads ~1GB, be patient)...")
    model = SentenceTransformer("intfloat/multilingual-e5-large")
    print("Model loaded.")

    # Extract the texts to embed
    texts = [chunk["text"] for chunk in chunks]
    ids = [chunk["id"] for chunk in chunks]
    card_names = [chunk["card_name"] for chunk in chunks]

    # Embed all chunks — this converts each text into a vector
    print("Embedding chunks... this may take a minute.")
    vectors = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_list=True
    )
    print(f"Created {len(vectors)} vectors.")

    # Set up ChromaDB — stores everything locally in a folder called dept_db
    client = chromadb.PersistentClient(path="./dept_db")

    # Delete old collection if it exists (useful when re-running)
    try:
        client.delete_collection("dept_guidelines")
    except:
        pass

    collection = client.create_collection(
        name="dept_guidelines",
        metadata={"description": "DEPT triage guidelines from deptriage.dk"}
    )

    # Store everything in the database
    collection.add(
        ids=ids,
        embeddings=vectors,
        documents=texts,
        metadatas=[{"card_name": card} for card in card_names]
    )

    print(f"\nDone. Stored {len(chunks)} chunks in ChromaDB at ./dept_db")
    print("Your DEPT vector database is ready.")

if __name__ == "__main__":
    embed_chunks()
