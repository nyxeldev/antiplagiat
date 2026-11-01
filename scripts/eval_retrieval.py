"""Offline retrieval/matching quality evaluation (feature/retrieval-eval-v1).

Measures backend.corpus candidate retrieval (A) and the EXISTING exact/
5-token-shingle matching algorithm (B, backend.comparison.matching.compare,
reused unchanged) against the hand-authored, ground-truth control set in
benchmarks/corpus-v1/. Also A/B's exactly three named axes: tsquery operator
(OR vs AND), chunk window (40/20 vs 80/40), candidate limit N (5 vs 20).

Database: creates its OWN disposable PostgreSQL cluster via
backend.tests.postgres_fixture.isolated_postgres() (the same mechanism the
test suite already uses) and tears it down when finished. NEVER connects to
the real antiplagiat database -- no ANTIPLAGIAT_DB_* value pointing at a real
instance is read or honoured; the harness only uses the config dict handed to
it by the disposable cluster.

No new dependency: stdlib only, plus the project's own psycopg/backend code
already required for the application itself.

Determinism: corpus document ids are derived deterministically from the
manifest's own id strings (uuid5), not randomised, so the SQL tie-break in
corpus.candidates() is reproducible. The benchmark text and manifest are
static files; nothing here calls random/time-seeded code. Run with --repeat 2
to verify two full passes produce byte-identical CSV output.

Usage (from the project root, with the project's own venv):
  .\\.venv\\Scripts\\python.exe scripts\\eval_retrieval.py
  .\\.venv\\Scripts\\python.exe scripts\\eval_retrieval.py --repeat 2
"""
import argparse
import csv
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import corpus, manage  # noqa: E402
from backend.benchmark.metrics import (  # noqa: E402
    aggregate_matching, aggregate_retrieval, span_to_token_set, token_prf1,
)
from backend.comparison.matching import compare, tokenize  # noqa: E402
from backend.persistence import database  # noqa: E402
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment  # noqa: E402

DEFAULT_BENCHMARK_DIR = ROOT / "benchmarks" / "corpus-v1"
NAMESPACE = uuid.UUID("a6e9b6a0-6c9a-4b7e-9c1a-9b6f3e9c1a6e")  # fixed, arbitrary; only for uuid5 determinism

CONFIGS = [
    {"name": "baseline_OR_chunk40-20_N5", "operator": "OR", "chunk_tokens": 40, "overlap_tokens": 20, "limit": 5},
    {"name": "ablation_tsquery_AND", "operator": "AND", "chunk_tokens": 40, "overlap_tokens": 20, "limit": 5},
    {"name": "ablation_chunk_80-40", "operator": "OR", "chunk_tokens": 80, "overlap_tokens": 40, "limit": 5},
    {"name": "ablation_candidates_N20", "operator": "OR", "chunk_tokens": 40, "overlap_tokens": 20, "limit": 20},
    # Opt-in uz-latin-v3 (rule-based suffix stripping, retrieval-only): same
    # chunking/operator/limit as the baseline, only the normalization axis
    # differs, so this isolates v3's effect on recall/precision from the
    # other three already-measured axes.
    {"name": "ablation_uz_latin_v3", "operator": "OR", "chunk_tokens": 40, "overlap_tokens": 20, "limit": 5,
     "normalization": "v3"},
]


def load_manifest(benchmark_dir=DEFAULT_BENCHMARK_DIR):
    manifest = json.loads((benchmark_dir / "manifest.json").read_text(encoding="utf-8"))
    for group in ("corpus", "queries"):
        for item in manifest[group]:
            item["_text"] = (benchmark_dir / item["file"]).read_text(encoding="utf-8")
    return manifest


def resolve_truth_spans(query_text, match_text_entries):
    """"__FULL_TEXT__" means the whole query document is ground truth (see
    manifest.json's note: paraphrase/morphological queries, whose entire
    content is derived from one source passage). Otherwise each entry is an
    exact substring, located with str.index() rather than hand-typed offsets.
    """
    if match_text_entries == ["__FULL_TEXT__"]:
        return [(0, len(query_text))]
    return [(query_text.index(snippet), query_text.index(snippet) + len(snippet))
            for snippet in match_text_entries]


def flat_doc(name, text):
    return {"name": name, "format": "txt", "text": text,
            "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(text)}]}


def wipe_corpus(admin_config):
    """Reset the disposable cluster's corpus tables between configs."""
    with database(admin_config) as conn:
        conn.execute("TRUNCATE antiplagiat.corpus_chunks, antiplagiat.corpus_documents")


def ingest_corpus(manifest, admin_user_id, cfg):
    """Returns {manifest corpus id: db uuid str}."""
    id_map = {}
    for entry in manifest["corpus"]:
        document_id = uuid.uuid5(NAMESPACE, entry["id"])
        metadata = {"title": entry["id"], "author_display": "Benchmark", "doc_type": "boshqa",
                    "year": None, "language_hint": entry["language"], "source_note": entry["topic"],
                    "permission_basis": "benchmarks/corpus-v1 synthetic control set (retrieval-eval-v1)",
                    "original_filename": Path(entry["file"]).name}
        extracted = {"text": entry["_text"], "name": entry["id"],
                    "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(entry["_text"])}]}
        corpus.add_document(metadata, extracted, admin_user_id, entry["_text"].encode("utf-8"),
                           chunk_tokens=cfg["chunk_tokens"], overlap_tokens=cfg["overlap_tokens"],
                           document_id=document_id)
        id_map[entry["id"]] = str(document_id)
    return id_map


def run_config(manifest, admin_user_id, cfg, id_map):
    reverse_map = {v: k for k, v in id_map.items()}
    corpus_by_id = {c["id"]: c for c in manifest["corpus"]}
    rows = []
    for q in manifest["queries"]:
        qtext = q["_text"]
        qtokens = tokenize(qtext)

        t0 = time.perf_counter()
        found, limit_used = corpus.candidates(qtokens, limit=cfg["limit"], operator=cfg["operator"],
                                              normalization=cfg.get("normalization", "v2"), text=qtext)
        retrieval_seconds = time.perf_counter() - t0
        ranked_ids = [reverse_map[c["id"]] for c in found]

        sources = [flat_doc(cid, corpus_by_id[cid]["_text"]) for cid in ranked_ids]
        t0 = time.perf_counter()
        if sources:
            result = compare(flat_doc(q["id"], qtext), sources)
            predicted_spans = [(m["document"]["start"], m["document"]["end"])
                               for source in result["sources"] for m in source["matches"]]
        else:
            predicted_spans = []
        matching_seconds = time.perf_counter() - t0

        predicted_tokens = span_to_token_set(qtokens, predicted_spans)
        truth_spans = resolve_truth_spans(qtext, q["match_text"])
        truth_tokens = span_to_token_set(qtokens, truth_spans)
        prf = token_prf1(predicted_tokens, truth_tokens)

        rows.append({
            "config": cfg["name"], "query_id": q["id"], "category": q["category"], "language": q["language"],
            "query_tokens": len(qtokens), "candidates_returned": len(ranked_ids), "candidate_limit": limit_used,
            "ranked_ids": ";".join(ranked_ids), "expected_sources": ";".join(q["expected_sources"]),
            "retrieval_seconds": round(retrieval_seconds, 5), "matching_seconds": round(matching_seconds, 5),
            "precision": prf["precision"], "recall": prf["recall"], "f1": prf["f1"],
            "true_positive_tokens": prf["true_positive_tokens"], "false_positive_tokens": prf["false_positive_tokens"],
            "truth_tokens": len(truth_tokens), "predicted_tokens": len(predicted_tokens),
            "ranked_ids_list": ranked_ids, "expected_ids_set": set(q["expected_sources"]),
        })
    return rows


def summarise(rows):
    retrieval_rows = [{"ranked_ids": r["ranked_ids_list"], "expected_ids": r["expected_ids_set"]} for r in rows]
    matching_rows = [{"precision": r["precision"], "recall": r["recall"], "f1": r["f1"],
                      "false_positive_tokens": r["false_positive_tokens"]} for r in rows]
    summary = {"n_queries": len(rows), "retrieval": aggregate_retrieval(retrieval_rows),
              "matching": aggregate_matching(matching_rows),
              "mean_retrieval_seconds": round(sum(r["retrieval_seconds"] for r in rows) / len(rows), 5),
              "mean_matching_seconds": round(sum(r["matching_seconds"] for r in rows) / len(rows), 5)}
    by_category = {}
    categories = sorted({r["category"] for r in rows})
    for category in categories:
        subset = [r for r in rows if r["category"] == category]
        sub_retrieval = [{"ranked_ids": r["ranked_ids_list"], "expected_ids": r["expected_ids_set"]} for r in subset]
        sub_matching = [{"precision": r["precision"], "recall": r["recall"], "f1": r["f1"],
                         "false_positive_tokens": r["false_positive_tokens"]} for r in subset]
        by_category[category] = {"n_queries": len(subset), "retrieval": aggregate_retrieval(sub_retrieval),
                                 "matching": aggregate_matching(sub_matching)}
    summary["by_category"] = by_category
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="corpus-v1",
                        help="Benchmark corpus folder under benchmarks/ (default: corpus-v1).")
    parser.add_argument("--repeat", type=int, default=1,
                        help="Run the whole harness this many times (fresh disposable cluster each "
                             "time) and diff the CSVs to verify determinism. Default 1 (no check).")
    args = parser.parse_args()

    benchmark_dir = ROOT / "benchmarks" / args.corpus
    results_dir = benchmark_dir / "results"
    manifest = load_manifest(benchmark_dir)
    results_dir.mkdir(exist_ok=True)
    csv_paths = []

    for attempt in range(1, args.repeat + 1):
        print(f"\n=== pass {attempt}/{args.repeat}: creating a disposable PostgreSQL cluster "
              f"(never the real antiplagiat database) ===")
        all_rows = []
        with isolated_postgres() as (admin_config, runtime_config):
            manage.migrate(admin_config)
            admin_user_id = manage.create_user(admin_config, "benchmark_admin",
                                               uuid.uuid4().hex, role="admin")
            with runtime_environment(runtime_config):
                for cfg in CONFIGS:
                    wipe_corpus(admin_config)
                    id_map = ingest_corpus(manifest, admin_user_id, cfg)
                    print(f"  config {cfg['name']:28} ingested {len(id_map)} corpus docs, "
                          f"running {len(manifest['queries'])} queries...")
                    rows = run_config(manifest, admin_user_id, cfg, id_map)
                    all_rows.extend(rows)
            # Cluster is dropped here, at the end of the `with` block, every pass.

        csv_path = results_dir / (f"raw.csv" if args.repeat == 1 else f"raw-pass{attempt}.csv")
        fieldnames = [k for k in all_rows[0].keys() if k not in ("ranked_ids_list", "expected_ids_set")]
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_rows:
                writer.writerow({k: row[k] for k in fieldnames})
        csv_paths.append(csv_path)
        print(f"  wrote {csv_path} ({len(all_rows)} rows)")

        if attempt == args.repeat:
            summary = {}
            for cfg in CONFIGS:
                cfg_rows = [r for r in all_rows if r["config"] == cfg["name"]]
                summary[cfg["name"]] = summarise(cfg_rows)
            summary_path = results_dir / "summary.json"
            summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"  wrote {summary_path}")

    if args.repeat > 1:
        # Everything except wall-clock timing must match exactly across passes.
        # retrieval_seconds/matching_seconds are real measurements of this
        # machine at this moment and are never claimed to be reproducible.
        def rows_without_timing(path):
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                row.pop("retrieval_seconds", None)
                row.pop("matching_seconds", None)
            return rows

        baseline_rows = rows_without_timing(csv_paths[0])
        identical = all(rows_without_timing(p) == baseline_rows for p in csv_paths[1:])
        print(f"\n=== determinism check: {args.repeat} passes, identical on every column except "
              f"retrieval_seconds/matching_seconds: {identical} ===")
        if not identical:
            sys.exit(1)


if __name__ == "__main__":
    main()
