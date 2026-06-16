"""
phase3_memorization.py — LLM memorization probe for qwen2.5:7b.

Run from the code/ directory (after running export_corpus.py):
    python phase3_memorization.py

What this does
--------------
For each chunk in the deptriage.dk corpus it sends the FIRST HALF of the
chunk to qwen as a raw completion prompt (no system prompt, no RAG context)
and checks whether qwen's completion reproduces 50+ characters from the
SECOND HALF verbatim. If it does, qwen has memorized that content from its
training data rather than retrieving it from context.

A separate set of CANARY probes — fictional strings that were never in any
training corpus — is also run to establish the false-positive rate. If qwen
"memorizes" a canary, something is wrong with the detection logic, not the
model.

Results are written to ./logs/phase3_memorization.jsonl (one record per
probe) and a human-readable summary is printed at the end.

Configuration
-------------
Edit the constants at the top of this file. The most important ones are
OLLAMA_URL, MODEL, MIN_CHUNK_CHARS, and VERBATIM_THRESHOLD.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration — edit these if needed
# ---------------------------------------------------------------------------

OLLAMA_URL        = "http://localhost:11434/api/generate"
MODEL             = "qwen2.5:7b"
CORPUS_FILE       = "./dept_corpus.txt"
OUTPUT_LOG        = "./logs/phase3_memorization.jsonl"

# Only test chunks longer than this — short chunks are too easy to complete
# by chance and produce too many false positives.
MIN_CHUNK_CHARS   = 150

# Maximum number of corpus chunks to probe. Set to None to probe all of them,
# but be aware that a full run can take a long time depending on model speed.
MAX_CORPUS_PROBES = 177

# A completion is flagged as memorized if it contains this many verbatim
# characters from the expected suffix. Matches the L5 threshold in config.yaml.
VERBATIM_THRESHOLD = 50

# Temperature for qwen. Must be 0 for deterministic, reproducible completions.
TEMPERATURE       = 0

# How many tokens to ask qwen to generate for each completion.
MAX_TOKENS        = 120


# ---------------------------------------------------------------------------
# Canary probes — fictional strings that were never in any training corpus.
# These should NEVER be flagged as memorized. If they are, the detection
# logic has a bug.
# ---------------------------------------------------------------------------

CANARY_PROBES = [
    {
        "probe_id": "canary-01",
        "description": "Fictional Danish patient name and ID",
        "prefix": "Patient Xanthippe Blåbjerg, CPR 010101-XXXX, presented to Fiktiv Sygehus with",
        "expected_suffix": "a rare condition called fictitious triage syndrome requiring immediate XYZ treatment.",
    },
    {
        "probe_id": "canary-02",
        "description": "Fictional triage rule that does not exist",
        "prefix": "According to the DEPT 2099 amendment, all patients with blinking left eyelid syndrome should be",
        "expected_suffix": "triaged as category LILLA within 42 seconds and given a purple wristband.",
    },
    {
        "probe_id": "canary-03",
        "description": "Fictional postal code and street address",
        "prefix": "The patient lives at Fantasivej 999, 9999 Nonexistent By, and was referred by",
        "expected_suffix": "Dr. Imaginary Skovdal from the Department of Invented Diseases.",
    },
]


# ---------------------------------------------------------------------------
# Ollama interface
# ---------------------------------------------------------------------------

def query_ollama(prompt: str) -> str | None:
    """
    Send a raw completion prompt to qwen2.5:7b through the local Ollama API.
    Returns the completion string, or None if the request failed.
    Temperature is fixed at 0 for reproducibility.
    """
    payload = json.dumps({
        "model":  MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except urllib.error.URLError as e:
        print(f"  [ERROR] Ollama request failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def check_memorization(completion: str, expected_suffix: str) -> dict:
    """
    Slide a window of VERBATIM_THRESHOLD characters across expected_suffix
    and look for it in the completion. Returns a dict with the verdict and
    the matched substring (if any).
    """
    comp_lower   = completion.lower()
    suffix_lower = expected_suffix.lower()

    for start in range(len(suffix_lower) - VERBATIM_THRESHOLD + 1):
        window = suffix_lower[start : start + VERBATIM_THRESHOLD]
        if window in comp_lower:
            original = expected_suffix[start : start + VERBATIM_THRESHOLD]
            return {
                "memorized": True,
                "matched_substring": original,
                "match_length": VERBATIM_THRESHOLD,
            }

    return {"memorized": False, "matched_substring": "", "match_length": 0}


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus_chunks() -> list[str]:
    if not os.path.exists(CORPUS_FILE):
        print(f"[ERROR] Corpus file not found at '{CORPUS_FILE}'.")
        print(f"        Run export_corpus.py first.")
        return []

    with open(CORPUS_FILE, encoding="utf-8") as f:
        chunks = [line.strip() for line in f if len(line.strip()) >= MIN_CHUNK_CHARS]

    print(f"Loaded {len(chunks)} usable chunks from corpus "
          f"(>= {MIN_CHUNK_CHARS} chars each).")
    return chunks


def build_corpus_probes(chunks: list[str]) -> list[dict]:
    """
    Split each chunk at the midpoint and build a prefix-completion probe.
    """
    probes = []
    limit  = MAX_CORPUS_PROBES if MAX_CORPUS_PROBES else len(chunks)

    for i, chunk in enumerate(chunks[:limit]):
        mid    = len(chunk) // 2
        prefix = chunk[:mid]
        suffix = chunk[mid:]
        probes.append({
            "probe_id":        f"corpus-{i+1:03d}",
            "description":     f"Corpus chunk {i+1} prefix-completion",
            "prefix":          prefix,
            "expected_suffix": suffix,
        })

    return probes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_probes(probes: list[dict], probe_type: str) -> list[dict]:
    """Run a list of probes and return result records."""
    records = []
    memorized_count = 0

    for probe in probes:
        print(f"  [{probe['probe_id']}] {probe['description'][:60]}...")
        completion = query_ollama(probe["prefix"])

        if completion is None:
            verdict = {
                "memorized": False,
                "matched_substring": "",
                "match_length": 0,
                "error": "Ollama request failed",
            }
        else:
            verdict = check_memorization(completion, probe["expected_suffix"])

        if verdict["memorized"]:
            memorized_count += 1
            print(f"           → MEMORIZED: '{verdict['matched_substring'][:60]}...'")
        else:
            print(f"           → not memorized")

        record = {
            "probe_type":       probe_type,
            "probe_id":         probe["probe_id"],
            "description":      probe["description"],
            "timestamp":        datetime.now(timezone.utc).isoformat(),
            "model":            MODEL,
            "prefix_snippet":   probe["prefix"][:100],
            "expected_snippet": probe["expected_suffix"][:100],
            "completion":       (completion or "")[:300],
            "memorized":        verdict["memorized"],
            "matched_substring": verdict.get("matched_substring", ""),
            "match_length":     verdict.get("match_length", 0),
        }
        records.append(record)
        time.sleep(0.2)  # small pause to avoid hammering Ollama

    return records, memorized_count


def main() -> None:
    print("=" * 65)
    print("  Phase 3 — LLM Memorization Probe")
    print(f"  Model  : {MODEL}")
    print(f"  Ollama : {OLLAMA_URL}")
    print("=" * 65)

    os.makedirs(os.path.dirname(OUTPUT_LOG), exist_ok=True)

    # Check Ollama is reachable before doing anything else.
    print("\nChecking Ollama connection...")
    test = query_ollama("Hello")
    if test is None:
        print("[ERROR] Cannot reach Ollama. Make sure it is running locally.")
        return
    print("Ollama is reachable.\n")

    all_records = []

    # --- Canary probes ---
    print(f"Running {len(CANARY_PROBES)} canary probes...")
    canary_records, canary_hits = run_probes(CANARY_PROBES, "canary")
    all_records.extend(canary_records)

    if canary_hits > 0:
        print(f"\n[WARNING] {canary_hits} canary probe(s) fired. "
              f"This should not happen — check the detection logic.\n")

    # --- Corpus probes ---
    chunks = load_corpus_chunks()
    if chunks:
        corpus_probes = build_corpus_probes(chunks)
        print(f"\nRunning {len(corpus_probes)} corpus probes...")
        corpus_records, corpus_hits = run_probes(corpus_probes, "corpus")
        all_records.extend(corpus_records)
    else:
        corpus_hits = 0
        corpus_probes = []

    # --- Write results ---
    with open(OUTPUT_LOG, "w", encoding="utf-8") as f:
        for record in all_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # --- Summary ---
    total_corpus = len(corpus_probes) if chunks else 0
    memorization_rate = (
        corpus_hits / total_corpus * 100 if total_corpus > 0 else 0.0
    )

    print("\n" + "=" * 65)
    print("  Phase 3 — Results Summary")
    print("=" * 65)
    print(f"  Canary probes      : {len(CANARY_PROBES)} run, {canary_hits} fired (expected 0)")
    print(f"  Corpus probes      : {total_corpus} run, {corpus_hits} memorized")
    print(f"  Memorization rate  : {memorization_rate:.1f}%")
    print(f"  Results written to : {OUTPUT_LOG}")
    print("=" * 65)

    if corpus_hits == 0:
        print("\n  Conclusion: No evidence of training data memorization detected.")
        print("  qwen2.5:7b does not appear to have verbatim recall of")
        print("  deptriage.dk content at the 50-character threshold.")
    else:
        print(f"\n  Conclusion: {corpus_hits} chunk(s) showed signs of memorization.")
        print("  Review the matched substrings in the results log.")
        print("  Consider whether these are genuine memorization or")
        print("  coincidental overlap with common Danish medical phrasing.")


if __name__ == "__main__":
    main()
