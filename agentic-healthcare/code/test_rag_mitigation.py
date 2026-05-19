import math
import random
from typing import List, Dict, Any

from utils import embedding_model, collection

TEST_QUERIES = [
    "chest tightness and shortness of breath",
    "severe headache and dizziness",
    "fever and sore throat for two days",
    "itchy skin rash on both arms",
    "possible broken bone after a fall",
]

SIGMAS = [0.0, 0.005, 0.01, 0.02]
TOP_K = 3


def add_gaussian_noise(vector: List[float], sigma: float = 0.01) -> List[float]:
    return [x + random.gauss(0, sigma) for x in vector]


def l2_normalize(vector: List[float]) -> List[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0:
        return vector
    return [x / norm for x in vector]


def query_collection_from_vector(query_vector: List[float], n_results: int = 3) -> Dict[str, Any]:
    return collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )


def baseline_retrieve(user_input: str, n_results: int = 3) -> Dict[str, Any]:
    query_vector = embedding_model.encode([user_input]).tolist()[0]
    return query_collection_from_vector(query_vector, n_results=n_results)


def mitigated_retrieve(user_input: str, sigma: float = 0.01, n_results: int = 3) -> Dict[str, Any]:
    query_vector = embedding_model.encode([user_input]).tolist()[0]
    noisy_vector = add_gaussian_noise(query_vector, sigma=sigma)
    normalized_vector = l2_normalize(noisy_vector)
    return query_collection_from_vector(normalized_vector, n_results=n_results)


def extract_card_names(results: Dict[str, Any]) -> List[str]:
    return [meta.get("card_name", "Unknown") for meta in results["metadatas"][0]]


def print_result_block(title: str, results: Dict[str, Any]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results.get("distances", [[None] * len(docs)])[0]

    for i, (doc, meta, dist) in enumerate(zip(docs, metas, distances), start=1):
        card = meta.get("card_name", "Unknown")
        preview = doc[:140].replace("\n", " ")
        print(f"{i}. card={card} | distance={dist:.6f} | preview={preview}")


def compare_overlap(baseline_cards: List[str], mitigated_cards: List[str]) -> int:
    return len(set(baseline_cards) & set(mitigated_cards))


def main():
    print("=" * 90)
    print("RAG MITIGATION TEST")
    print("=" * 90)
    print("This script compares baseline retrieval vs mitigated retrieval using Gaussian noise + L2 normalization.\n")

    for query in TEST_QUERIES:
        print("\n" + "=" * 90)
        print(f"QUERY: {query}")
        print("=" * 90)

        baseline = baseline_retrieve(query, n_results=TOP_K)
        baseline_cards = extract_card_names(baseline)
        print_result_block("BASELINE (sigma=0.0)", baseline)

        for sigma in SIGMAS[1:]:
            mitigated = mitigated_retrieve(query, sigma=sigma, n_results=TOP_K)
            mitigated_cards = extract_card_names(mitigated)
            overlap = compare_overlap(baseline_cards, mitigated_cards)

            print_result_block(f"MITIGATED (sigma={sigma})", mitigated)
            print(f"Overlap with baseline top-{TOP_K} card names: {overlap}/{TOP_K}")

    print("\n" + "=" * 90)
    print("INTERPRETATION")
    print("=" * 90)
    print("- If sigma=0.005 or 0.01 gives similar top cards, the mitigation preserves utility.")
    print("- If sigma=0.02 starts returning unrelated cards, that sigma is probably too high.")
    print("- Small ranking changes are acceptable; major topic drift means retrieval quality is degrading.")


if __name__ == "__main__":
    main()