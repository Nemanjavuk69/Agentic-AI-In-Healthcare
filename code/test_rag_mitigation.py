import csv
import math
import random
import statistics
import time
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt

from utils import embedding_model, collection, add_gaussian_noise, l2_normalize


TEST_QUERIES = [
    "chest tightness and shortness of breath",
    "severe headache and dizziness",
    "fever and sore throat for two days",
    "itchy skin rash on both arms",
    "possible broken bone after a fall",
    "persistent cough with mild breathing discomfort",
    "abdominal pain and vomiting since morning",
    "swollen ankle after twisting it while walking",
    "burning when urinating and lower stomach pain",
    "high fever with chills and weakness",
    "sudden back pain after lifting something heavy",
    "red itchy eyes with mild swelling"
]

SIGMAS = [0.0, 0.005, 0.01, 0.02]
TOP_K = 3
RUNS_PER_SIGMA = 10
RANDOM_SEED = 42

RAW_RESULTS_CSV = "rag_mitigation_results.csv"
SUMMARY_RESULTS_CSV = "rag_mitigation_summary.csv"
AGGREGATE_PLOT_PNG = "rag_mitigation_tradeoff.png"


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def query_collection_from_vector(query_vector: List[float], n_results: int = TOP_K) -> Dict[str, Any]:
    return collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )


def extract_card_names(results: Dict[str, Any]) -> List[str]:
    return [meta.get("card_name", "Unknown") for meta in results["metadatas"][0]]


def top1_card(results: Dict[str, Any]) -> str:
    cards = extract_card_names(results)
    return cards[0] if cards else "Unknown"


def top3_overlap(baseline_cards: List[str], test_cards: List[str]) -> int:
    return len(set(baseline_cards) & set(test_cards))


def mean_distance(results: Dict[str, Any]) -> float:
    distances = results.get("distances", [[]])[0]
    if not distances:
        return float("nan")
    return sum(distances) / len(distances)


def retrieve_from_text(user_input: str, sigma: float, n_results: int = TOP_K) -> Dict[str, Any]:
    query_vector = embedding_model.encode([user_input]).tolist()[0]
    if sigma > 0:
        query_vector = add_gaussian_noise(query_vector, sigma=sigma)
        query_vector = l2_normalize(query_vector)
    return query_collection_from_vector(query_vector, n_results=n_results)


def run_benchmark() -> List[Dict[str, Any]]:
    random.seed(RANDOM_SEED)
    rows = []

    for query in TEST_QUERIES:
        baseline_vector = embedding_model.encode([query]).tolist()[0]
        baseline_results = query_collection_from_vector(baseline_vector, n_results=TOP_K)
        baseline_cards = extract_card_names(baseline_results)
        baseline_top1 = top1_card(baseline_results)
        baseline_mean_dist = mean_distance(baseline_results)

        for sigma in SIGMAS:
            runs = 1 if sigma == 0.0 else RUNS_PER_SIGMA

            for run_idx in range(1, runs + 1):
                start = time.perf_counter()

                if sigma == 0.0:
                    noisy_vector = baseline_vector[:]
                    test_results = baseline_results
                else:
                    noisy_vector = add_gaussian_noise(baseline_vector[:], sigma=sigma)
                    noisy_vector = l2_normalize(noisy_vector)
                    test_results = query_collection_from_vector(noisy_vector, n_results=TOP_K)

                elapsed_ms = (time.perf_counter() - start) * 1000.0

                test_cards = extract_card_names(test_results)
                test_top1 = top1_card(test_results)
                test_mean_dist = mean_distance(test_results)
                overlap = top3_overlap(baseline_cards, test_cards)
                cos_sim = cosine_similarity(baseline_vector, noisy_vector)

                rows.append({
                    "query": query,
                    "sigma": sigma,
                    "run": run_idx,
                    "baseline_top1": baseline_top1,
                    "test_top1": test_top1,
                    "top1_match": int(baseline_top1 == test_top1),
                    "top3_overlap": overlap,
                    "top3_overlap_ratio": overlap / TOP_K,
                    "cosine_similarity": cos_sim,
                    "baseline_mean_distance": baseline_mean_dist,
                    "test_mean_distance": test_mean_dist,
                    "distance_shift": test_mean_dist - baseline_mean_dist,
                    "elapsed_ms": elapsed_ms,
                    "baseline_top3": " | ".join(baseline_cards),
                    "test_top3": " | ".join(test_cards)
                })

    return rows


def summarize_results(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary = []

    for sigma in SIGMAS:
        sigma_rows = [r for r in rows if r["sigma"] == sigma]

        summary.append({
            "sigma": sigma,
            "n_trials": len(sigma_rows),
            "top1_match_rate": round(statistics.mean(r["top1_match"] for r in sigma_rows), 4),
            "top3_overlap_mean": round(statistics.mean(r["top3_overlap"] for r in sigma_rows), 4),
            "top3_overlap_ratio_mean": round(statistics.mean(r["top3_overlap_ratio"] for r in sigma_rows), 4),
            "cosine_similarity_mean": round(statistics.mean(r["cosine_similarity"] for r in sigma_rows), 6),
            "distance_shift_mean": round(statistics.mean(r["distance_shift"] for r in sigma_rows), 6),
            "elapsed_ms_mean": round(statistics.mean(r["elapsed_ms"] for r in sigma_rows), 3),
            "top1_match_std": round(statistics.pstdev(r["top1_match"] for r in sigma_rows), 4),
            "top3_overlap_std": round(statistics.pstdev(r["top3_overlap"] for r in sigma_rows), 4),
            "cosine_similarity_std": round(statistics.pstdev(r["cosine_similarity"] for r in sigma_rows), 6),
        })

    return summary


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def save_aggregate_plot(summary_csv: str, output_png: str) -> None:
    df = pd.read_csv(summary_csv)

    plt.figure(figsize=(8, 5))
    plt.plot(df["sigma"], df["top1_match_rate"], marker="o", linewidth=2.5, label="Top-1 match rate")
    plt.plot(df["sigma"], df["top3_overlap_ratio_mean"], marker="s", linewidth=2.5, label="Top-3 overlap ratio")
    plt.plot(df["sigma"], df["cosine_similarity_mean"], marker="^", linewidth=2.5, label="Cosine similarity")

    plt.xlabel("Noise level (sigma)")
    plt.ylabel("Score")
    plt.ylim(0, 1.05)
    plt.title("Privacy-utility trade-off in RAG retrieval")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_png, dpi=300, bbox_inches="tight")
    plt.close()


def print_summary(summary_rows: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 108)
    print("RAG RETRIEVER MITIGATION BENCHMARK")
    print("=" * 108)
    print(f"Queries: {len(TEST_QUERIES)} | Top-k: {TOP_K} | Runs per sigma: {RUNS_PER_SIGMA} | Seed: {RANDOM_SEED}")
    print("-" * 108)
    print(
        f"{'Sigma':<10}"
        f"{'Trials':<10}"
        f"{'Top1 Rate':<14}"
        f"{'Top3 Mean':<14}"
        f"{'Top3 Ratio':<14}"
        f"{'Cos Sim':<14}"
        f"{'Dist Shift':<14}"
        f"{'Latency ms':<12}"
    )
    print("-" * 108)

    for row in summary_rows:
        print(
            f"{row['sigma']:<10}"
            f"{row['n_trials']:<10}"
            f"{row['top1_match_rate']:<14}"
            f"{row['top3_overlap_mean']:<14}"
            f"{row['top3_overlap_ratio_mean']:<14}"
            f"{row['cosine_similarity_mean']:<14}"
            f"{row['distance_shift_mean']:<14}"
            f"{row['elapsed_ms_mean']:<12}"
        )

    print("-" * 108)
    print("Interpretation:")
    print("- Higher top1/top3 values mean better retrieval utility preservation.")
    print("- Lower cosine similarity means the perturbed embedding is less faithful to the original query.")
    print("- Increasing sigma should reduce fidelity, but too much noise may reduce retrieval relevance.")
    print(f"- Detailed trial results saved to: {RAW_RESULTS_CSV}")
    print(f"- Aggregate summary saved to: {SUMMARY_RESULTS_CSV}")
    print(f"- Aggregate plot saved to: {AGGREGATE_PLOT_PNG}")


def main():
    rows = run_benchmark()
    summary_rows = summarize_results(rows)

    write_csv(RAW_RESULTS_CSV, rows)
    write_csv(SUMMARY_RESULTS_CSV, summary_rows)
    save_aggregate_plot(SUMMARY_RESULTS_CSV, AGGREGATE_PLOT_PNG)
    print_summary(summary_rows)


if __name__ == "__main__":
    main()