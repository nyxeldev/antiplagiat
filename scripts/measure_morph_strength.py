"""Measure how "morphological" (suffix-only) a rewritten query really is,
relative to its source corpus document (feature/uz-morph-v3, A-band fix-up).

Why this exists: a first pass at strengthening benchmarks/corpus-v2's
morphological queries used synonym substitution and clause rewrites to kill
every 5-token shingle match. That over-corrects -- it turns "morphological"
queries into "paraphrase" queries, which already exist as their own
category. This script gives an objective, reproducible number instead of
eyeballing the text, so the category boundary stays honest.

TOKENIZATION: backend.comparison.matching.tokenize() -- the SAME tokenizer
the real matching algorithm uses (NFKC/casefold/apostrophe normalization,
word-level splitting). All three metrics below operate on the ``value``
field of its tokens, lowercased, never on raw source text.

ALIGNMENT: difflib.SequenceMatcher(a=source_tokens, b=query_tokens). This
aligns the two token sequences allowing for a handful of inserted/deleted
tokens (e.g. a dropped "ham", an added predicate "-dir" as its own token)
without destroying alignment the way strict positional indexing would. Each
opcode is one of:
  - "equal"   -- a run of tokens identical in both sequences, in order.
  - "replace" -- a source-token run and a query-token run of possibly
                 different lengths standing at the same position; paired up
                 index-by-index over the SHORTER of the two.
  - "insert"  -- query tokens with no corresponding source tokens at all
                 (a word added that doesn't replace anything).
  - "delete"  -- source tokens dropped from the query entirely.

CONTENT WORD: any token whose value, after lowercasing, is not in
FUNCTION_WORDS and has at least MIN_CONTENT_WORD_LEN characters. This is a
coarse stopword filter (conjunctions, pronouns, postpositions, short
copulas) -- not a POS tagger. Numbers and bare punctuation tokens that slip
through tokenize() are excluded by the length check in practice.

THE THREE METRICS, PRECISELY:

(a) suffix_changed_ratio -- of ALL content-word positions found by walking
    every opcode (equal AND replace, source-token side), what fraction were
    changed in the query AND still "share a stem" with the source word
    (see shares_stem)? This is the fix for the earlier, broken version of
    this script: that version computed the ratio only over words already
    inside "replace" opcodes, so a long run of completely untouched
    "equal" content words contributed NOTHING to the denominator -- a text
    that was half verbatim and half suffix-edited could score 100%. Here,
    an "equal" content word counts as a content word that did NOT change,
    dragging the ratio down exactly as it should.

    suffix_changed_ratio = (# content words changed AND stem-preserved)
                            / (# content words total, equal + replaced)

    A word counts as "changed" only inside a replace opcode where it has an
    aligned query-side counterpart (paired positionally within the shorter
    of the two slice lengths). "equal" content words are, by definition,
    unchanged. Inserted/deleted words (the `inserted_words` / `deleted_words`
    fields) are reported separately and are NOT folded into either the
    numerator or the denominator of this ratio, since an insertion is not a
    suffix change on an existing word -- it is a new word, which the B1
    instruction prohibits outright for this category (see pure_substitution
    below).

(b) longest_unchanged_run -- the longest single "equal" opcode, in tokens
    (not characters, not sentences): the longest run of consecutive tokens
    that are byte-for-byte identical to the source, in the same order.

(c) shingle_overlap_5token -- the SHARED (set-intersection) count of 5-token
    shingles between query and source: |shingles(query) & shingles(source)|.
    This is deliberately an intersection, not a sum of each side's shingle
    count ("umumiy" = shared/common here, not "jami" = total/combined).
    Each unique 5-gram counts once regardless of how many times it repeats
    in either text.

(d) pure_substitution -- True only when inserted_words == 0 AND
    deleted_words == 0 for the whole query, i.e. the query is a pure
    word-for-word substitution of the source with no token added or
    removed anywhere ("insert"/"delete" opcodes, and the unpaired leftover
    of an unequal-length "replace" block, both count against this). This
    is the feature/uz-morph-v3 B1 instruction's mechanical, zero-tolerance
    gate: "Qo'shilgan so'z: 0. Olib tashlangan so'z: 0." As of B1,
    suffix_changed_ratio has NO required threshold -- pure_substitution is
    the only hard pass/fail check; a low suffix ratio on a
    pure_substitution=True query is accepted as the category's honest
    difficulty, not a defect to chase.

A high suffix_changed_ratio and a high shingle_overlap/long unchanged run
CAN legitimately coexist only for a SHORT text where a handful of proper
nouns/dates/terms force unavoidable overlap relative to its small size --
not for whole untouched clauses. Where it happens, the mechanism is
visible in per_query[...]["longest_unchanged_run_tokens"], printed below,
so a human can check it is a name/date/term rather than a forgotten clause.

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
MIN_CONTENT_WORD_LEN = 4  # shorter tokens are treated as function words regardless

# Coarse Uzbek function-word list: conjunctions, pronouns, postpositions,
# short copulas/particles. Not exhaustive -- just enough that "va", "ham",
# "bu", "u", "esa" etc. don't get counted as "content" in either direction.
FUNCTION_WORDS = {
    "va", "ham", "esa", "bu", "u", "bu", "shu", "ular", "uning", "uni",
    "bilan", "uchun", "kabi", "ya'ni", "lekin", "ammo", "biroq", "yoki",
    "yoxud", "ba'zi", "har", "ko'p", "oz", "edi", "emas", "bo'lib", "deb",
    "ko'ra", "qarab", "qadar", "tomonidan",
}


def shares_stem(word_a, word_b, min_prefix=MIN_SHARED_PREFIX):
    """Heuristic only -- no real Uzbek morphological analyzer is used.
    Two words "share a stem" if they share a leading substring of at least
    min_prefix characters (case-insensitive). This is intentionally crude;
    it is a signal for a human to sanity-check, not a linguistic ground
    truth. Identical words trivially share a stem.
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


def is_content_word(value, min_len=MIN_CONTENT_WORD_LEN):
    v = value.lower()
    return len(v) >= min_len and v not in FUNCTION_WORDS


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
    content_words_total = 0
    content_words_changed_stem_preserved = 0
    content_words_changed_non_suffix = 0
    inserted_words = 0
    deleted_words = 0

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            unchanged_run_lengths.append(i2 - i1)
            for src_word in s_vals[i1:i2]:
                if is_content_word(src_word):
                    content_words_total += 1
                    # unchanged by construction -- not suffix_changed
        elif tag == "replace":
            src_slice = s_vals[i1:i2]
            qry_slice = q_vals[j1:j2]
            paired_len = min(len(src_slice), len(qry_slice))
            for k in range(paired_len):
                src_word, qry_word = src_slice[k], qry_slice[k]
                if is_content_word(src_word):
                    content_words_total += 1
                    if shares_stem(src_word, qry_word):
                        content_words_changed_stem_preserved += 1
                    else:
                        content_words_changed_non_suffix += 1
            # Any leftover on either side (unequal replace-block lengths)
            # is an insertion or deletion, not a suffix change -- tracked
            # separately so it can't inflate the suffix-changed ratio.
            if len(qry_slice) > paired_len:
                inserted_words += len(qry_slice) - paired_len
            if len(src_slice) > paired_len:
                deleted_words += len(src_slice) - paired_len
        elif tag == "insert":
            inserted_words += j2 - j1
        elif tag == "delete":
            deleted_words += i2 - i1

    longest_unchanged_run = max(unchanged_run_lengths) if unchanged_run_lengths else 0

    suffix_changed_ratio = (
        content_words_changed_stem_preserved / content_words_total
        if content_words_total
        else None
    )

    q_shingles = shingles(q_tokens)
    s_shingles = shingles(s_tokens)
    shingle_overlap = len(q_shingles & s_shingles)

    return {
        "query_tokens": len(q_tokens),
        "source_tokens": len(s_tokens),
        "content_words_total": content_words_total,
        "content_words_changed_stem_preserved": content_words_changed_stem_preserved,
        "content_words_changed_non_suffix": content_words_changed_non_suffix,
        "suffix_changed_ratio": suffix_changed_ratio,
        "longest_unchanged_run_tokens": longest_unchanged_run,
        "shingle_overlap_5token": shingle_overlap,
        "inserted_words": inserted_words,
        "deleted_words": deleted_words,
        # True only when the query is a pure word-for-word substitution of
        # the source: no token was added or dropped anywhere (every
        # "replace" block paired up completely, with no insert/delete
        # opcodes at all). This is a mechanical, zero-tolerance check --
        # feature/uz-morph-v3's B1 instruction prohibits any added or
        # removed word in the morphological category, full stop.
        "pure_substitution": inserted_words == 0 and deleted_words == 0,
    }


def token_level_ground_truth(query_text, source_text):
    """Per-query-token ground truth for whether a token COULD legitimately be
    matched by a lexical/stemming matcher against source_text, derived from
    the SAME difflib.SequenceMatcher alignment as measure() above -- but
    classifying EVERY query token position (content word or not), not just
    content words, since backend.comparison.matching.compare() shingles over
    every token's value/stem, not only content words.

    Why this exists (feature/morph-token-ground-truth): the benchmark's
    manifest.json marks morphological/paraphrase queries' ground truth as
    "__FULL_TEXT__" (the whole query document). That is the right convention
    for precision_at_k-style retrieval metrics, but it makes token_prf1()'s
    MATCHING-level precision mechanically 1.0 for these categories --
    predicted_tokens is always a subset of "the whole document" -- regardless
    of whether the matched tokens are actually correct. This function gives a
    real, token-level ground truth for the morphological category instead
    (it does NOT replace or remove "__FULL_TEXT__" in manifest.json; see
    docs/benchmarks/uz-morph-v3-matching.md).

    Each query token index falls into exactly one of:
      - "equal"           -- byte-for-byte identical to its aligned source
                              token; a real match is trivially expected.
      - "replace_stem"    -- substituted for a different source token that
                              shares_stem() with it (a suffix-only change);
                              a stemmer that strips the right suffix SHOULD
                              be able to match it.
      - "replace_synonym" -- substituted for a source token that does NOT
                              share a stem (a true synonym/different word,
                              not a suffix change); no lexical/stemming
                              matcher can legitimately find this, so it is
                              EXCLUDED from ground truth.
      - "inserted"        -- no source counterpart at all (only possible
                              when the query is not a pure substitution, see
                              pure_substitution above); excluded from ground
                              truth for the same reason as "replace_synonym".
    A source-side "delete" opcode has no query token index at all, so it
    contributes to neither list.

    Returns a dict:
      - query_token_count: len(tokenize(query_text))
      - expected_match_token_indices: sorted query token indices where a
        correct lexical matcher COULD legitimately report a match ("equal"
        + "replace_stem"). This is the real ground truth to use in place of
        "the whole document" for morphological-category precision/recall.
      - non_matchable_token_indices: sorted query token indices where ANY
        match reported by the algorithm is necessarily a FALSE one
        ("replace_synonym" + "inserted") -- not a suffix variant of the
        source, so stemming cannot legitimately bridge it.
      - counts: {"equal", "replace_stem", "replace_synonym", "inserted"} ->
        token counts, for a quick sanity check against query_token_count.

    Invariant (see TokenLevelGroundTruthTests.test_every_index_classified_exactly_once):
    sorted(expected_match_token_indices + non_matchable_token_indices) ==
    list(range(query_token_count)) -- every query token is classified exactly
    once, since difflib's opcodes partition the query sequence with no gaps
    or overlaps.
    """
    q_tokens = tokenize(query_text)
    s_vals = [t["value"] for t in tokenize(source_text)]
    q_vals = [t["value"] for t in q_tokens]

    matcher = difflib.SequenceMatcher(a=s_vals, b=q_vals, autojunk=False)
    expected = []
    non_matchable = []
    counts = {"equal": 0, "replace_stem": 0, "replace_synonym": 0, "inserted": 0}

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            expected.extend(range(j1, j2))
            counts["equal"] += j2 - j1
        elif tag == "replace":
            src_slice = s_vals[i1:i2]
            qry_slice = q_vals[j1:j2]
            paired_len = min(len(src_slice), len(qry_slice))
            for k in range(paired_len):
                index = j1 + k
                if shares_stem(src_slice[k], qry_slice[k]):
                    expected.append(index)
                    counts["replace_stem"] += 1
                else:
                    non_matchable.append(index)
                    counts["replace_synonym"] += 1
            if len(qry_slice) > paired_len:
                non_matchable.extend(range(j1 + paired_len, j2))
                counts["inserted"] += len(qry_slice) - paired_len
            # Leftover on the source side (src longer than qry) is a
            # deletion: no query token index exists for it, so nothing is
            # recorded here -- consistent with the plain "delete" branch.
        elif tag == "insert":
            non_matchable.extend(range(j1, j2))
            counts["inserted"] += j2 - j1
        # "delete": source-only tokens, no query-side index to record.

    return {
        "query_token_count": len(q_tokens),
        "expected_match_token_indices": sorted(expected),
        "non_matchable_token_indices": sorted(non_matchable),
        "counts": counts,
    }


def main():
    manifest = json.loads((BENCHMARK_DIR / "manifest.json").read_text(encoding="utf-8"))
    corpus_text = {
        c["id"]: (BENCHMARK_DIR / c["file"]).read_text(encoding="utf-8")
        for c in manifest["corpus"]
    }

    results = {}
    print(
        f"{'query_id':<26} {'pure':>6} {'suffix%':>8} {'content':>8} {'longest_run':>12} "
        f"{'shingles':>9} {'ins/del':>8}"
    )
    for q in manifest["queries"]:
        if q["category"] != "morphological":
            continue
        query_text = (BENCHMARK_DIR / q["file"]).read_text(encoding="utf-8")
        source_text = corpus_text[q["expected_sources"][0]]
        row = measure(query_text, source_text)
        row["token_ground_truth"] = token_level_ground_truth(query_text, source_text)
        results[q["id"]] = row
        ratio = row["suffix_changed_ratio"]
        ratio_str = f"{ratio:.0%}" if ratio is not None else "n/a"
        ins_del = f"{row['inserted_words']}/{row['deleted_words']}"
        pure_str = "True" if row["pure_substitution"] else "FALSE"
        print(
            f"{q['id']:<26} {pure_str:>6} {ratio_str:>8} {row['content_words_total']:>8} "
            f"{row['longest_unchanged_run_tokens']:>12} {row['shingle_overlap_5token']:>9} "
            f"{ins_del:>8}"
        )

    ratios = [r["suffix_changed_ratio"] for r in results.values() if r["suffix_changed_ratio"] is not None]
    runs = [r["longest_unchanged_run_tokens"] for r in results.values()]
    shingle_counts = [r["shingle_overlap_5token"] for r in results.values()]
    n_pure = sum(1 for r in results.values() if r["pure_substitution"])

    summary = {
        "n_queries": len(results),
        "n_pure_substitution": n_pure,
        "all_pure_substitution": n_pure == len(results),
        "mean_suffix_changed_ratio": sum(ratios) / len(ratios) if ratios else None,
        "min_suffix_changed_ratio": min(ratios) if ratios else None,
        "mean_longest_unchanged_run_tokens": sum(runs) / len(runs) if runs else None,
        "max_longest_unchanged_run_tokens": max(runs) if runs else None,
        "mean_shingle_overlap_5token": sum(shingle_counts) / len(shingle_counts) if shingle_counts else None,
        "max_shingle_overlap_5token": max(shingle_counts) if shingle_counts else None,
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
