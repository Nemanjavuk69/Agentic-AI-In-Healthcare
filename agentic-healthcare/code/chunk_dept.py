import json

def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            cut = text.rfind("\n", start, end)
            if cut != -1:
                end = cut
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start = end - overlap
    return chunks

def process_raw_file():
    with open("dept_raw.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    all_chunks = []
    chunk_id = 0

    for card in raw_data:
        chunks = chunk_text(card["text"])
        for chunk in chunks:
            all_chunks.append({
                "id": f"dept_chunk_{chunk_id}",
                "card_name": card["card_name"],   # e.g. "Brystsmerter"
                "source_url": card["source_url"],
                "text": chunk
            })
            chunk_id += 1

    with open("dept_chunks.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"Created {len(all_chunks)} chunks → saved to dept_chunks.json")

if __name__ == "__main__":
    process_raw_file()
