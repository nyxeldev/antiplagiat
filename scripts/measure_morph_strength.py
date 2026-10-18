"""Measure how "morphological" (suffix-only) a rewritten query really is,
relative to its source corpus document (feature/uz-morph-v3, A-band fix-up).

Why this exists: a first pass at strengthening benchmarks/corpus-v2's
morphological queries used synonym substitution and clause rewrites to kill
every 5-token shingle match. That over-corrects -- it turns "morphological"
queries into "paraphrase" queries, which already exist as their own
category. This script gives an objective, reproducible number instead of
eyeballing the text, so the category boundary stays honest:

  (a) suffix_changed_ratio -- of the words that differ between query and
      source, what fraction still share the source word's STEM (a crude
      shared-prefix heuristic) rather than being an unrelated synonym?
  (b) longest_unchanged_run -- the longest run of consecutive tokens that
      are identical to the source (word-for-word), using difflib alignment
      so minor insertions (a dropped/added "ham", "esa") don't break
      alignment the way strict positional indexing would.
  (c) shingle_overlap -- count of 5-token shingles identical to the source
      (same metric used in the retrieval/matching harness). This is
      EXPECTED to be > 0 when proper nouns, dates or technical terms force
      a run of unchanged tokens -- that is not a defect, per AGENTS.md A-band
      instruction: "0 umumiy shingle" MAJBURIY EMAS.

Pure stdlib (difflib), reuses backend.comparison.matching.tokenize so the
same tokenization rules apply as the real matching algorithm. No network,
no DB -- reads only the benchmarks/corpus-v2 manifest and text files.

Usage (from project root, with the project's own venv):
  .\\.venv\\Scripts\\python.exe scripts\\measure_morph_strength.py
"""
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.comparison.matching import tokenize  # noqa: E402

BENCHMARK_DIR = ROOT / "benchmarks" / "corpus-v2"
MIN_SHARED_PREFIX = 3  # crude stem heuristic: this many leading chars must match


def shares_stem(word_a, word_b, min_prefix=MIN_SHARED_PREFIX):
    """Heuristic only -- no real Uzbek morphological analyzer is used.
    Two words "share a stem" if one is a prefix of the other, or they share
    a leading substring of at least min_prefix characters. This is
    intentionally crude; it is a signal for a human to sanity-check, not a
    linguistic ground truth.
    """
    a, b = word_a.lower(), word_b.lower()
    if a == b:
        return True
    shorter = min(len(a), len(b))
    if shorter < min_prefix:
        return False
    prefix_len = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        prefix_len += 1
    return prefix_len >= min_prefix


def shingles(tokens, n=5):
    vals = [t["value"] for t in tokens]
    return set(tuple(vals[i : i + n]) for i in range(len(vals) - n + 1))


def measure(query_text, source_text):
    q_tokens = tokenize(query_text)
    s_tokens = tokenize(source_text)
    q_vals = [t["value"] for t in q_tokens]
    s_vals = [t["value"] for t in s_tokens]

    matcher = difflib.SequenceMatcher(a=s_vals, b=q_vals, autojunk=False)
    opcodes = matcher.get_opcodes()

    unchanged_run_lengths = []
    changed_pairs = []  # (source_word, query_word) for same-length replace blocks
    unmatched_query_words = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            unchanged_run_lengths.append(i2 - i1)
        elif tag == "replace":
            # Pair up positionally within the replace block when lengths match;
            # otherwise each source/query word in the shorter range is still
            # compared against its aligned counterpart on a best-effort basis.
            src_slice = s_vals[i1:i2]
            qry_slice = q_vals[j1:j2]
            for k in range(min(len(src_slice), len(qry_slice))):
                changed_pairs.append((src_slice[k], qry_slice[k]))
            unmatched_query_words += abs(len(qry_slice) - len(src_slice))
        elif tag == "insert":
            unmatched_query_words += j2 - j1
        # "delete" (source word dropped entirely) doesn't count against the query

    longest_unchanged_run = max(unchanged_run_lengths) if unchanged_run_lengths else 0

    suffix_changed = sum(1 for src, qry in changed_pairs if shares_stem(src, qry))
    non_suffix_changed = len(changed_pairs) - suffix_changed
    total_changed_words = len(changed_pairs)
    suffix_changed_ratio = (
        suffix_changed / total_changed_words if total_changed_words else None
    )

    q_shingles = shingles(q_tokens)
    s_shingles = shingles(s_tokens)
    shingle_overlap = len(q_shingles & s_shingles)

    return {
        "query_tokens": len(q_tokens),
        "source_tokens": len(s_tokens),
        "changed_word_pairs": total_changed_words,
        "suffix_changed_words": suffix_changed,
        "non_suffix_changed_words": non_suffix_changed,
        "suffix_changed_ratio": suffix_changed_ratio,
        "longest_unchanged_run": longest_unchanged_run,
        "shingle_overlap_5token": shingle_overlap,
        "unmatched_query_words": unmatched_query_words,
    }


def main():
    manifest = json.loads((BENCHMARK_DIR / "manifest.json").read_text(encoding="utf-8"))
    corpus_text = {
        c["id"]: (BENCHMARK_DIR / c["file"]).read_text(encoding="utf-8")
        for c in manifest["corpus"]
    }

    results = {}
    print(f"{'query_id':<26} {'suffix%':>8} {'changed':>8} {'longest_run':>12} {'shingles':>9}")
    for q in manifest["queries"]:
        if q["category"] != "morphological":
            continue
        query_text = (BENCHMARK_DIR / q["file"]).read_text(encoding="utf-8")
        source_text = corpus_text[q["expected_sources"][0]]
        row = measure(query_text, source_text)
        results[q["id"]] = row
        ratio = row["suffix_changed_ratio"]
        ratio_str = f"{ratio:.0%}" if ratio is not None else "n/a"
        print(
            f"{q['id']:<26} {ratio_str:>8} {row['changed_word_pairs']:>8} "
            f"{row['longest_unchanged_run']:>12} {row['shingle_overlap_5token']:>9}"
        )

    ratios = [r["suffix_changed_ratio"] for r in results.values() if r["suffix_changed_ratio"] is not None]
    runs = [r["longest_unchanged_run"] for r in results.values()]
    shingle_counts = [r["shingle_overlap_5token"] for r in results.values()]

    summary = {
        "n_queries": len(results),
        "mean_suffix_changed_ratio": sum(ratios) / len(ratios) if ratios else None,
        "min_suffix_changed_ratio": min(ratios) if ratios else None,
        "mean_longest_unchanged_run": sum(runs) / len(runs) if runs else None,
        "max_longest_unchanged_run": max(runs) if runs else None,
        "mean_shingle_overlap": sum(shingle_counts) / len(shingle_counts) if shingle_counts else None,
        "max_shingle_overlap": max(shingle_counts) if shingle_counts else None,
    }
    print()
    print("=== Summary (mean / worst case across 15 morphological queries) ===")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    out = {"per_query": results, "summary": summary}
    out_path = BENCHMARK_DIR / "morph_strength.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
