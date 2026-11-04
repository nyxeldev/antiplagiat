"""Real, token-level precision/recall/F1 for the `morphological` benchmark
category (feature/morph-token-ground-truth, docs/benchmarks/
uz-morph-v3-matching.md §3/§8).

Why this exists: benchmarks/corpus-v2/manifest.json marks morphological
queries' ground truth as "__FULL_TEXT__" (the whole query document). That
convention makes backend.benchmark.metrics.token_prf1()'s MATCHING-level
precision mechanically 1.0 for this category -- predicted_tokens is always a
subset of "the whole document" -- regardless of whether the matched tokens
are actually correct. This script uses the real, per-token ground truth
scripts/measure_morph_strength.py's token_level_ground_truth() derives from
its difflib alignment instead (benchmarks/corpus-v2/morph_strength.json's
"token_ground_truth" field per query), and recomputes precision/recall/F1
against THAT.

Retrieval is bypassed entirely -- each query is compared directly against
its own manifest-recorded expected_sources[0] -- the same choice already
made for docs/benchmarks/uz-morph-v3-matching.md §5's percent-inflation
analysis, and justified the same way: retrieval's own recall/precision is a
separate, already-measured axis (§1/§2), and matching is independent of
which retrieval normalization picked the candidate (docs/decisions.md §5).
"off" and "retrieval" use the identical matching stage (matching_normalization
defaults to "uz-latin-v2" either way), so they collapse into one row here,
exactly as in §5.

Pure stdlib + the project's own backend code. No database, no network.

Usage (from the project root, with the project's own venv):
  .\\.venv\\Scripts\\python.exe scripts\\measure_morph_token_precision.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.benchmark.metrics import aggregate_matching, span_to_token_set, token_prf1  # noqa: E402
from backend.comparison.matching import compare, tokenize  # noqa: E402

BENCHMARK_DIR = ROOT / "benchmarks" / "corpus-v2"
MODES = [("off/retrieval (matching_normalization=uz-latin-v2)", "uz-latin-v2"),
         ("retrieval+matching (matching_normalization=uz-latin-v3)", "uz-latin-v3")]


def flat_doc(name, text):
    return {"name": name, "format": "txt", "text": text,
            "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(text)}]}


def main():
    manifest = json.loads((BENCHMARK_DIR / "manifest.json").read_text(encoding="utf-8"))
    strength = json.loads((BENCHMARK_DIR / "morph_strength.json").read_text(encoding="utf-8"))
    corpus_text = {c["id"]: (BENCHMARK_DIR / c["file"]).read_text(encoding="utf-8") for c in manifest["corpus"]}

    queries = [q for q in manifest["queries"] if q["category"] == "morphological"]
    assert len(queries) == 15, f"expected 15 morphological queries, found {len(queries)}"

    per_mode_rows = {label: [] for label, _ in MODES}
    overmatch_examples = {label: [] for label, _ in MODES}

    print(f"{'query_id':<24} {'mode':<12} {'precision':>9} {'recall':>7} {'f1':>7} {'over-matched':>13}")
    for q in queries:
        query_text = (BENCHMARK_DIR / q["file"]).read_text(encoding="utf-8")
        source_text = corpus_text[q["expected_sources"][0]]
        q_tokens = tokenize(query_text)
        truth_tokens = set(strength["per_query"][q["id"]]["token_ground_truth"]["expected_match_token_indices"])

        for label, matching_normalization in MODES:
            result = compare(flat_doc(q["id"], query_text), [flat_doc(q["expected_sources"][0], source_text)],
                             matching_normalization=matching_normalization)
            predicted_spans = [(m["document"]["start"], m["document"]["end"])
                               for source in result["sources"] for m in source["matches"]]
            predicted_tokens = span_to_token_set(q_tokens, predicted_spans)
            prf = token_prf1(predicted_tokens, truth_tokens)
            per_mode_rows[label].append(prf)

            overmatched = sorted(predicted_tokens - truth_tokens)
            if overmatched:
                words = [q_tokens[i]["value"] for i in overmatched]
                overmatch_examples[label].append({"query_id": q["id"], "token_indices": overmatched, "words": words})

            p_str = f"{prf['precision']:.4f}" if prf["precision"] is not None else "n/a"
            print(f"{q['id']:<24} {matching_normalization:<12} {p_str:>9} "
                  f"{prf['recall']:>7.4f} {prf['f1']:>7.4f} {len(overmatched):>13}")

    print()
    print("=== Macro-average across 15 morphological queries (real token ground truth) ===")
    for label, _ in MODES:
        agg = aggregate_matching(per_mode_rows[label])
        total_overmatched = sum(len(e["token_indices"]) for e in overmatch_examples[label])
        n_affected = len(overmatch_examples[label])
        print(f"{label}: precision={agg['precision']:.4f} (n={agg['precision_n']}/15) "
              f"recall={agg['recall']:.4f} f1={agg['f1']:.4f} "
              f"false_positive_queries={agg['false_positive_queries']}/15 "
              f"over-matched tokens={total_overmatched} (in {n_affected}/15 queries)")

    print()
    print("=== Over-matched token examples (predicted but NOT in real ground truth) ===")
    for label, _ in MODES:
        print(f"-- {label} --")
        if not overmatch_examples[label]:
            print("  (none)")
        for example in overmatch_examples[label]:
            print(f"  {example['query_id']}: {example['words']}")

    out = {
        "mode_labels": [label for label, _ in MODES],
        "per_query": {label: per_mode_rows[label] for label, _ in MODES},
        "overmatch_examples": overmatch_examples,
    }
    out_path = BENCHMARK_DIR / "results" / "morph_token_precision.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
