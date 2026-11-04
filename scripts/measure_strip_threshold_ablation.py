"""MIN_WORD_LEN_TO_STRIP ablation (7/6/5), re-measured with REAL token-level
ground truth (feature/strip-threshold-recheck).

Why this exists: docs/benchmarks/uz-morph-v3-d2-ablation.md measured this
same three values (2026-10-18), but BEFORE token-level ground truth existed
-- morphological precision there was still the __FULL_TEXT__ tautology, and
matching was still pinned to uz-latin-v2 (the "retrieval+matching" mode did
not exist yet). This script re-measures with:

  1. scripts/measure_morph_strength.py's token_level_ground_truth() for the
     morphological category's REAL precision/recall/F1, under
     matching_normalization="uz-latin-v3" (retrieval+matching).
  2. verbatim/partial/quoted precision/recall/F1 under the same mode, to
     confirm they stay unchanged across all three threshold values.
  3. hard_negative+unrelated false positives through the REAL retrieval ->
     matching pipeline (candidates() then compare(), both v3), since those
     14 queries have no expected_sources to compare against directly and
     D2-ablation's "0 FP" result was measured with v2 MATCHING, not
     v3-matching -- a lower MIN_WORD_LEN_TO_STRIP could in principle make
     an unrelated word's stem collide with a wrongly-retrieved candidate's,
     which D2-ablation could not have caught.
  4. A fresh foreign-word (en/ru corpus) over-stripping count, same method
     as docs/benchmarks/uz-morph-v3-d1-fixes.md's D1.2/C1.4.

MIN_WORD_LEN_TO_STRIP is monkeypatched on the live uz_latin_v3 module for
each value, in one process -- backend/comparison/uz_latin_v3.py's committed
value (7) is never edited on disk.

Needs a local PostgreSQL (same disposable-cluster mechanism as
scripts/eval_retrieval.py and the backend integration test suite) only for
part 3; parts 1/2/4 bypass retrieval entirely, same methodology as
docs/benchmarks/uz-morph-v3-matching.md §4/§6.

Usage (from the project root, with the project's own venv):
  .\\.venv\\Scripts\\python.exe scripts\\measure_strip_threshold_ablation.py
"""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import corpus, manage  # noqa: E402
from backend.benchmark.metrics import aggregate_matching, span_to_token_set, token_prf1  # noqa: E402
from backend.comparison import uz_latin_v3  # noqa: E402
from backend.comparison.matching import compare, tokenize  # noqa: E402
from backend.persistence import database  # noqa: E402
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment  # noqa: E402

BENCHMARK_DIR = ROOT / "benchmarks" / "corpus-v2"
THRESHOLDS = [7, 6, 5]
DEFAULT_THRESHOLD = uz_latin_v3.MIN_WORD_LEN_TO_STRIP  # 7, read before any patching
NAMESPACE = uuid.UUID("a6e9b6a0-6c9a-4b7e-9c1a-9b6f3e9c1a6e")  # same fixed namespace as scripts/eval_retrieval.py


def flat_doc(name, text):
    return {"name": name, "format": "txt", "text": text,
            "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(text)}]}


def resolve_truth_spans(query_text, match_text_entries):
    if match_text_entries == ["__FULL_TEXT__"]:
        return [(0, len(query_text))]
    return [(query_text.index(s), query_text.index(s) + len(s)) for s in match_text_entries]


def load_manifest():
    manifest = json.loads((BENCHMARK_DIR / "manifest.json").read_text(encoding="utf-8"))
    for group in ("corpus", "queries"):
        for item in manifest[group]:
            item["_text"] = (BENCHMARK_DIR / item["file"]).read_text(encoding="utf-8")
    return manifest


def wipe_corpus(admin_config):
    with database(admin_config) as conn:
        conn.execute("TRUNCATE antiplagiat.corpus_chunks, antiplagiat.corpus_documents")


def ingest_corpus(manifest, admin_user_id):
    id_map = {}
    for entry in manifest["corpus"]:
        document_id = uuid.uuid5(NAMESPACE, entry["id"])
        metadata = {"title": entry["id"], "author_display": "Benchmark", "doc_type": "boshqa",
                    "year": None, "language_hint": entry["language"], "source_note": entry["topic"],
                    "permission_basis": "benchmarks/corpus-v2 synthetic control set (strip-threshold-recheck)",
                    "original_filename": Path(entry["file"]).name}
        extracted = {"text": entry["_text"], "name": entry["id"],
                    "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(entry["_text"])}]}
        corpus.add_document(metadata, extracted, admin_user_id, entry["_text"].encode("utf-8"),
                           chunk_tokens=40, overlap_tokens=20, document_id=document_id)
        id_map[entry["id"]] = str(document_id)
    return id_map


# --- Part 1: foreign-word over-stripping, no DB -----------------------------

def foreign_overstrip(manifest):
    occurrences, seen_words, examples = 0, set(), []
    for entry in manifest["corpus"]:
        if entry["language"] not in ("en", "ru"):
            continue
        text = entry["_text"]
        for token in tokenize(text):
            raw = text[token["start"]:token["end"]]
            stemmed = uz_latin_v3.stem(raw)
            if stemmed != raw:
                occurrences += 1
                key = raw.lower()
                if key not in seen_words:
                    seen_words.add(key)
                    examples.append(f"{raw}->{stemmed}")
    return {"occurrences": occurrences, "unique_words": len(seen_words), "examples": examples}


# --- Part 2: positive categories, retrieval bypassed (§4/§6 method) --------

def positive_category_rows(manifest, strength):
    queries = [q for q in manifest["queries"] if q["expected_sources"]]
    corpus_text = {c["id"]: c["_text"] for c in manifest["corpus"]}
    by_category = {}
    for q in queries:
        query_text = q["_text"]
        source_text = corpus_text[q["expected_sources"][0]]
        q_tokens = tokenize(query_text)
        result = compare(flat_doc(q["id"], query_text), [flat_doc(q["expected_sources"][0], source_text)],
                         matching_normalization="uz-latin-v3")
        predicted_spans = [(m["document"]["start"], m["document"]["end"])
                           for source in result["sources"] for m in source["matches"]]
        predicted_tokens = span_to_token_set(q_tokens, predicted_spans)

        if q["category"] == "morphological":
            truth_tokens = set(strength["per_query"][q["id"]]["token_ground_truth"]["expected_match_token_indices"])
        else:
            truth_spans = resolve_truth_spans(query_text, q["match_text"])
            truth_tokens = span_to_token_set(q_tokens, truth_spans)

        prf = token_prf1(predicted_tokens, truth_tokens)
        overmatched = sorted(predicted_tokens - truth_tokens)
        by_category.setdefault(q["category"], []).append({
            **prf, "query_id": q["id"],
            "overmatched_tokens": len(overmatched),
            "overmatched_words": [q_tokens[i]["value"] for i in overmatched],
        })
    return by_category


# --- Part 3: hard_negative/unrelated FP, through REAL retrieval+matching ---

def negative_category_fp(manifest, id_map):
    reverse_map = {v: k for k, v in id_map.items()}
    corpus_by_id = {c["id"]: c["_text"] for c in manifest["corpus"]}
    negatives = [q for q in manifest["queries"] if q["category"] in ("hard_negative", "unrelated")]
    rows = []
    for q in negatives:
        qtext = q["_text"]
        qtokens = tokenize(qtext)
        found, _ = corpus.candidates(qtokens, limit=5, operator="OR", normalization="v3", text=qtext)
        ranked_ids = [reverse_map[c["id"]] for c in found]
        if ranked_ids:
            sources = [flat_doc(cid, corpus_by_id[cid]) for cid in ranked_ids]
            result = compare(flat_doc(q["id"], qtext), sources, matching_normalization="uz-latin-v3")
            predicted_spans = [(m["document"]["start"], m["document"]["end"])
                               for source in result["sources"] for m in source["matches"]]
        else:
            predicted_spans = []
        predicted_tokens = span_to_token_set(qtokens, predicted_spans)
        prf = token_prf1(predicted_tokens, set())
        rows.append({"query_id": q["id"], "category": q["category"], "ranked_ids": ranked_ids,
                     "false_positive_tokens": prf["false_positive_tokens"]})
    return rows


def main():
    manifest = load_manifest()
    strength = json.loads((BENCHMARK_DIR / "morph_strength.json").read_text(encoding="utf-8"))

    results = {}
    with isolated_postgres() as (admin_config, runtime_config):
        manage.migrate(admin_config)
        admin_user_id = manage.create_user(admin_config, "benchmark_admin", uuid.uuid4().hex, role="admin")
        with runtime_environment(runtime_config):
            for threshold in THRESHOLDS:
                print(f"\n=== MIN_WORD_LEN_TO_STRIP = {threshold} ===")
                uz_latin_v3.MIN_WORD_LEN_TO_STRIP = threshold

                foreign = foreign_overstrip(manifest)
                print(f"  chet so'z noto'g'ri qirqilgan: {foreign['occurrences']} marta "
                      f"({foreign['unique_words']} ta noyob so'z)")

                positive = positive_category_rows(manifest, strength)
                for category in ("morphological", "verbatim", "partial", "quoted", "paraphrase"):
                    rows = positive.get(category, [])
                    if not rows:
                        continue
                    agg = aggregate_matching(rows)
                    overmatched = sum(r["overmatched_tokens"] for r in rows)
                    print(f"  {category:14} n={len(rows):<3} precision={agg['precision']:.4f} "
                          f"recall={agg['recall']:.4f} f1={agg['f1']:.4f} overmatched_tokens={overmatched}")

                wipe_corpus(admin_config)
                id_map = ingest_corpus(manifest, admin_user_id)
                negative_rows = negative_category_fp(manifest, id_map)
                fp_queries = sum(1 for r in negative_rows if r["false_positive_tokens"] > 0)
                total_fp_tokens = sum(r["false_positive_tokens"] for r in negative_rows)
                print(f"  hard_negative+unrelated (n={len(negative_rows)}): "
                      f"{fp_queries} so'rovda yolg'on musbat, jami {total_fp_tokens} token")

                results[str(threshold)] = {
                    "foreign_overstrip": foreign,
                    "positive_categories": positive,
                    "negative_categories": negative_rows,
                }

    uz_latin_v3.MIN_WORD_LEN_TO_STRIP = DEFAULT_THRESHOLD  # restore, hygiene only (process exits anyway)

    out_path = BENCHMARK_DIR / "results" / "strip_threshold_ablation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
