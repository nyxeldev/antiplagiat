"""Pure, dependency-free metric functions for the retrieval evaluation harness
(scripts/eval_retrieval.py). No database, no I/O, no randomness: every function
here is a deterministic function of its arguments, which is what makes the
harness's own determinism check meaningful.

Two separate levels, intentionally never mixed into one number:

  A) Retrieval level  -- did candidate selection (corpus.candidates()) return
     the right corpus DOCUMENTS, in the right order?
  B) Matching level    -- within a query document, did the EXISTING exact/
     shingle algorithm (backend.comparison.matching.compare) flag the right
     CHARACTER RANGES as matched, compared to hand-authored ground truth?
"""
from math import isnan


# --- A) Retrieval level ------------------------------------------------

def recall_at_k(ranked_ids, expected_ids, k):
    """Fraction of expected_ids present in the top k of ranked_ids.

    Undefined (returns None) when expected_ids is empty: there is nothing to
    recall, so the query contributes nothing to a recall average rather than
    a potentially misleading 0 or 1. Callers average only the non-None values.
    """
    if not expected_ids:
        return None
    found = set(ranked_ids[:k]) & set(expected_ids)
    return len(found) / len(expected_ids)


def precision_at_k(ranked_ids, expected_ids, k):
    """Fraction of the top k ranked_ids that are actually expected.

    Divides by min(k, len(ranked_ids)) rather than a flat k, so a query whose
    corpus genuinely has fewer than k plausible candidates is not penalised
    for k's size rather than for a real retrieval mistake. Undefined (None)
    only when nothing at all was retrieved.

    Unlike recall_at_k, this is NOT undefined when expected_ids is empty: a
    hard-negative or unrelated-text query still has a well-defined precision
    (0.0, unless retrieval happens to return nothing at all), and that 0.0 is
    exactly the useful signal -- it shows retrieval confidently returning
    candidates for a document that should have matched none.
    """
    top = ranked_ids[:k]
    if not top:
        return None
    found = set(top) & set(expected_ids)
    return len(found) / len(top)


def reciprocal_rank(ranked_ids, expected_ids):
    """1 / (rank of the first relevant id), 1-based; 0.0 if none found.

    Returns None when expected_ids is empty (nothing to find), consistent
    with recall_at_k.
    """
    if not expected_ids:
        return None
    expected = set(expected_ids)
    for position, identifier in enumerate(ranked_ids, start=1):
        if identifier in expected:
            return 1.0 / position
    return 0.0


def _mean(values):
    kept = [v for v in values if v is not None]
    if not kept:
        return None
    return sum(kept) / len(kept)


def aggregate_retrieval(per_query_rows):
    """per_query_rows: iterable of dicts with keys ranked_ids, expected_ids.

    Returns the mean of each metric across queries that had a non-empty
    expected_ids (queries with no expected source, e.g. unrelated/negative
    categories, are excluded from these means by design -- see recall_at_k).
    Also reports how many queries actually contributed to each mean, since a
    mean over very few queries is easy to misread as more solid than it is.
    """
    r1 = [recall_at_k(r["ranked_ids"], r["expected_ids"], 1) for r in per_query_rows]
    r5 = [recall_at_k(r["ranked_ids"], r["expected_ids"], 5) for r in per_query_rows]
    r10 = [recall_at_k(r["ranked_ids"], r["expected_ids"], 10) for r in per_query_rows]
    p5 = [precision_at_k(r["ranked_ids"], r["expected_ids"], 5) for r in per_query_rows]
    rr = [reciprocal_rank(r["ranked_ids"], r["expected_ids"]) for r in per_query_rows]
    return {
        "recall_at_1": _mean(r1), "recall_at_1_n": sum(v is not None for v in r1),
        "recall_at_5": _mean(r5), "recall_at_5_n": sum(v is not None for v in r5),
        "recall_at_10": _mean(r10), "recall_at_10_n": sum(v is not None for v in r10),
        "precision_at_5": _mean(p5), "precision_at_5_n": sum(v is not None for v in p5),
        "mrr": _mean(rr), "mrr_n": sum(v is not None for v in rr),
    }


# --- B) Matching level ---------------------------------------------------

def span_to_token_set(tokens, char_spans):
    """Token indices whose [start,end) token span overlaps any char span.

    tokens: the list backend.comparison.matching.tokenize() returns for the
    query document (each item has "start"/"end" character offsets).
    char_spans: iterable of (start, end) character ranges, end-exclusive,
    Unicode code points -- the same offset convention the rest of the app
    uses (see docs/architecture.md, "offset_unit").
    """
    covered = set()
    for cs, ce in char_spans:
        for index, token in enumerate(tokens):
            if token["start"] < ce and token["end"] > cs:
                covered.add(index)
    return covered


def token_prf1(predicted_tokens, truth_tokens):
    """Precision/recall/F1 over token-index sets, with explicit empty-set rules.

    - truth empty, predicted empty  -> P=R=F1=1.0 (correctly found nothing)
    - truth empty, predicted non-empty -> P=0.0 (false positive), R undefined
      (nothing to recall) so R is reported as None, F1 follows P/R: 0.0 here
      since P is 0.
    - truth non-empty, predicted empty -> P undefined (None), R=0.0, F1=0.0.
    """
    predicted_tokens, truth_tokens = set(predicted_tokens), set(truth_tokens)
    true_positive = len(predicted_tokens & truth_tokens)
    if not truth_tokens and not predicted_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0,
                "false_positive_tokens": 0, "true_positive_tokens": 0}
    precision = (true_positive / len(predicted_tokens)) if predicted_tokens else None
    recall = (true_positive / len(truth_tokens)) if truth_tokens else None
    if precision is None:
        f1 = 0.0
    elif recall is None:
        f1 = 0.0
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1,
            "false_positive_tokens": len(predicted_tokens - truth_tokens),
            "true_positive_tokens": true_positive}


def aggregate_matching(per_query_rows):
    """per_query_rows: iterable of token_prf1() result dicts (one per query).

    Macro-average (mean of per-query scores, not pooled token counts), which
    weights every query document equally regardless of its length -- a 2000
    token verbatim copy does not get to dominate a 40 token paraphrase.
    """
    precisions = [r["precision"] for r in per_query_rows]
    recalls = [r["recall"] for r in per_query_rows]
    f1s = [r["f1"] for r in per_query_rows]
    return {
        "precision": _mean(precisions), "precision_n": sum(v is not None for v in precisions),
        "recall": _mean(recalls), "recall_n": sum(v is not None for v in recalls),
        "f1": _mean(f1s), "f1_n": len(f1s),
        "false_positive_queries": sum(1 for r in per_query_rows if r["false_positive_tokens"] > 0),
    }


def is_finite_number(value):
    return isinstance(value, (int, float)) and not isnan(value)
