"""Unit tests for scripts.measure_morph_strength: every expected value here
is hand-computed in the test itself (in a comment), not derived from the
code under test. No database, no files, no randomness.

scripts/ is not a package under backend/, so it is reached by inserting the
project root onto sys.path, same as measure_morph_strength.py does for
backend itself.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import measure_morph_strength as mms  # noqa: E402


class SharesStemTests(unittest.TestCase):
    def test_identical_words_share_stem(self):
        self.assertTrue(mms.shares_stem("falsafasi", "falsafasi"))

    def test_suffix_only_change_shares_stem(self):
        # "falsafa" + "si" (3rd-person possessive) vs "falsafa" + "lari"
        # (plural possessive) -- same 7-char root "falsafa".
        self.assertTrue(mms.shares_stem("falsafasi", "falsafalari"))

    def test_unrelated_word_does_not_share_stem(self):
        # Synonym substitution, not a suffix change -- no shared prefix at all.
        self.assertFalse(mms.shares_stem("al-kindiy", "donishmand"))

    def test_short_words_require_full_match(self):
        # Below MIN_SHARED_PREFIX (3), only an exact match counts.
        self.assertTrue(mms.shares_stem("va", "va"))
        self.assertFalse(mms.shares_stem("va", "bu"))


class IsContentWordTests(unittest.TestCase):
    def test_function_words_excluded(self):
        self.assertFalse(mms.is_content_word("va"))
        self.assertFalse(mms.is_content_word("bilan"))

    def test_short_word_excluded_even_if_not_listed(self):
        # "edi" has length 3 < MIN_CONTENT_WORD_LEN (4); it is also listed,
        # but the length check alone would already exclude it.
        self.assertFalse(mms.is_content_word("edi"))

    def test_long_non_function_word_is_content(self):
        self.assertTrue(mms.is_content_word("falsafasi"))


class MeasureTests(unittest.TestCase):
    """Each case uses a 5-word source/query pair (padded to clear the
    tokenizer's 5-token minimum) so hand-counting is tractable."""

    def test_identical_text_scores_full_unchanged(self):
        text = "katta oq uy juda yaxshi"
        row = mms.measure(text, text)
        # Every token is an "equal" opcode -- nothing changed, so there are
        # no changed content words at all, and the ratio is undefined (no
        # denominator contribution from unchanged words is wrong -- content
        # words ARE counted from "equal" opcodes, just with 0 changed).
        # Content words (len>=4, not in FUNCTION_WORDS): "katta"(5), "yaxshi"(6).
        # "oq"(2) too short, "uy"(2) too short, "juda"(4) -> length 4, not a
        # function word -> IS content. So content words = katta, juda, yaxshi = 3.
        self.assertEqual(row["content_words_total"], 3)
        self.assertEqual(row["content_words_changed_stem_preserved"], 0)
        self.assertEqual(row["suffix_changed_ratio"], 0.0)
        # Whole 5-token text is one unchanged run.
        self.assertEqual(row["longest_unchanged_run_tokens"], 5)
        self.assertEqual(row["inserted_words"], 0)
        self.assertEqual(row["deleted_words"], 0)

    def test_single_suffix_change_is_detected_and_counted(self):
        source = "u katta falsafasi haqida yozdi"
        query = "u katta falsafalari haqida yozdi"
        row = mms.measure(query, source)
        # Content words in source (len>=4, not function word): "katta"(5),
        # "falsafasi"(9), "haqida"(6), "yozdi"(5) -> 4 content words.
        # "falsafasi" -> "falsafalari": shares a 7-char prefix ("falsafa")
        # >= MIN_SHARED_PREFIX -> counted as suffix-changed.
        # The other 3 content words are in "equal" runs -> unchanged.
        self.assertEqual(row["content_words_total"], 4)
        self.assertEqual(row["content_words_changed_stem_preserved"], 1)
        self.assertAlmostEqual(row["suffix_changed_ratio"], 1 / 4)
        # Longest equal run: either "u katta" (2) before, or "haqida yozdi"
        # (2) after the replaced word -- both length 2.
        self.assertEqual(row["longest_unchanged_run_tokens"], 2)

    def test_synonym_substitution_is_not_suffix_changed(self):
        source = "u katta falsafasi haqida yozdi"
        query = "u katta donishmandlik haqida yozdi"
        row = mms.measure(query, source)
        # "falsafasi" -> "donishmandlik" shares no meaningful prefix:
        # counted as changed but NOT suffix-preserved.
        self.assertEqual(row["content_words_total"], 4)
        self.assertEqual(row["content_words_changed_stem_preserved"], 0)
        self.assertEqual(row["suffix_changed_ratio"], 0.0)

    def test_long_unchanged_block_drags_ratio_down_even_with_other_changes(self):
        # Regression test for the bug this rewrite fixes: a previous version
        # of this script only computed suffix_changed_ratio over words
        # already inside "replace" opcodes, so a long untouched "equal"
        # block contributed NOTHING to the denominator and could not drag
        # the ratio down -- a half-verbatim, half-suffix-edited text could
        # score 100%. Source: 8 content words total; only the LAST one
        # ("yozdi" -> "yozgan", suffix-changed) differs. The first seven
        # words ("katta shahar markazida islom bilimdonlari yig'ilib")
        # are completely untouched.
        source = "katta shahar markazida islom bilimdonlari yig'ilib yozdi"
        query = "katta shahar markazida islom bilimdonlari yig'ilib yozgan"
        row = mms.measure(query, source)
        # Content words (len>=4, not function word): katta, shahar,
        # markazida, islom, bilimdonlari, yig'ilib, yozdi -> 7 total
        # ("islom" has length 5, qualifies).
        self.assertEqual(row["content_words_total"], 7)
        self.assertEqual(row["content_words_changed_stem_preserved"], 1)
        # The broken version of this script would have reported 100% here
        # (1 changed word, stem preserved, ratio computed only over changed
        # words). The fixed version must show the long untouched run
        # dragging the ratio down to 1/7.
        self.assertAlmostEqual(row["suffix_changed_ratio"], 1 / 7)
        self.assertEqual(row["longest_unchanged_run_tokens"], 6)

    def test_inserted_word_is_not_folded_into_suffix_changed_ratio(self):
        source = "katta shahar markazida bozor ochildi"
        query = "katta shahar eski markazida bozor ochildi"
        row = mms.measure(query, source)
        # "eski" is a pure insertion (no source counterpart) -- it must be
        # tracked in inserted_words, not silently counted as a content word
        # match or a suffix change.
        self.assertEqual(row["inserted_words"], 1)
        self.assertEqual(row["deleted_words"], 0)
        self.assertFalse(row["pure_substitution"])

    def test_pure_substitution_true_when_no_insert_or_delete(self):
        source = "u katta falsafasi haqida yozdi"
        query = "u katta falsafalari haqida yozdi"
        row = mms.measure(query, source)
        self.assertEqual(row["inserted_words"], 0)
        self.assertEqual(row["deleted_words"], 0)
        self.assertTrue(row["pure_substitution"])

    def test_pure_substitution_false_on_deleted_word(self):
        source = "katta shahar eski markazida bozor ochildi"
        query = "katta shahar markazida bozor ochildi"
        row = mms.measure(query, source)
        # "eski" exists only on the source side -- a pure deletion.
        self.assertEqual(row["inserted_words"], 0)
        self.assertEqual(row["deleted_words"], 1)
        self.assertFalse(row["pure_substitution"])

    def test_pure_substitution_false_on_unequal_replace_block(self):
        # difflib reports "eski qadimgi" (2 source words) / "zamonaviy"
        # (1 query word) as a single "replace" opcode of UNEQUAL length
        # (not a separate insert/delete opcode). The leftover source word
        # must still count as a deletion so pure_substitution catches it
        # even though it never appears as its own "delete" opcode.
        source = "katta eski qadimgi shahar bozor ochildi"
        query = "katta zamonaviy shahar bozor ochildi"
        row = mms.measure(query, source)
        self.assertEqual(row["deleted_words"], 1)
        self.assertFalse(row["pure_substitution"])

    def test_shingle_overlap_counts_shared_not_total(self):
        # 6 tokens -> two 5-token shingles per text.
        source = "bir ikki uch tort besh olti"
        query_same = "bir ikki uch tort besh olti"
        query_different = "yetti sakkiz to'qqiz o'n on bir"
        row_same = mms.measure(query_same, source)
        row_diff = mms.measure(query_different, source)
        # Identical text: both 5-grams shared -> intersection size 2, not
        # the sum of each side's shingle count (which would be 4).
        self.assertEqual(row_same["shingle_overlap_5token"], 2)
        # Completely different text: no shared shingles.
        self.assertEqual(row_diff["shingle_overlap_5token"], 0)


class TokenLevelGroundTruthTests(unittest.TestCase):
    """Each case is hand-computed in the comment, same convention as
    MeasureTests above -- these are the inputs feature/morph-token-ground-truth
    adds (uz-morph-v3-matching.md §8/§3): real, token-level ground truth for
    the morphological category, in place of manifest.json's "__FULL_TEXT__"
    convention (which stays unchanged for retrieval-level metrics)."""

    def test_identical_text_every_token_is_equal(self):
        text = "katta oq uy juda yaxshi"
        row = mms.token_level_ground_truth(text, text)
        self.assertEqual(row["query_token_count"], 5)
        self.assertEqual(row["expected_match_token_indices"], [0, 1, 2, 3, 4])
        self.assertEqual(row["non_matchable_token_indices"], [])
        self.assertEqual(row["counts"], {"equal": 5, "replace_stem": 0, "replace_synonym": 0, "inserted": 0})

    def test_suffix_only_change_is_expected_to_match(self):
        source = "u katta falsafasi haqida yozdi"
        query = "u katta falsafalari haqida yozdi"
        row = mms.token_level_ground_truth(query, source)
        # Query tokens: u(0) katta(1) falsafalari(2) haqida(3) yozdi(4).
        # Only index 2 is a "replace" (falsafasi -> falsafalari), and it
        # shares a stem -- so ALL 5 query tokens are expected-match, none
        # excluded, even though one of them came from a "replace" opcode.
        self.assertEqual(row["expected_match_token_indices"], [0, 1, 2, 3, 4])
        self.assertEqual(row["non_matchable_token_indices"], [])
        self.assertEqual(row["counts"]["equal"], 4)
        self.assertEqual(row["counts"]["replace_stem"], 1)

    def test_synonym_substitution_is_excluded_from_ground_truth(self):
        source = "u katta falsafasi haqida yozdi"
        query = "u katta donishmandlik haqida yozdi"
        row = mms.token_level_ground_truth(query, source)
        # Query tokens: u(0) katta(1) donishmandlik(2) haqida(3) yozdi(4).
        # Index 2 replaces "falsafasi" with a non-stem-sharing word -- no
        # lexical/stemming matcher can legitimately find this, so it must be
        # excluded from expected_match_token_indices and listed as
        # non_matchable instead.
        self.assertEqual(row["expected_match_token_indices"], [0, 1, 3, 4])
        self.assertEqual(row["non_matchable_token_indices"], [2])
        self.assertEqual(row["counts"]["replace_synonym"], 1)

    def test_inserted_word_is_non_matchable_not_expected(self):
        source = "katta shahar markazida bozor ochildi"
        query = "katta shahar eski markazida bozor ochildi"
        row = mms.token_level_ground_truth(query, source)
        # Query tokens: katta(0) shahar(1) eski(2) markazida(3) bozor(4)
        # ochildi(5). "eski" (index 2) has no source counterpart at all.
        self.assertEqual(row["expected_match_token_indices"], [0, 1, 3, 4, 5])
        self.assertEqual(row["non_matchable_token_indices"], [2])
        self.assertEqual(row["counts"]["inserted"], 1)

    def test_deleted_source_word_leaves_every_query_token_classified(self):
        source = "katta shahar eski markazida bozor ochildi"
        query = "katta shahar markazida bozor ochildi"
        row = mms.token_level_ground_truth(query, source)
        # The deletion ("eski") lives only on the source side -- it has no
        # query token index, so it must not shrink or gap the query's own
        # index range: every one of the 5 query tokens is still classified.
        self.assertEqual(row["query_token_count"], 5)
        self.assertEqual(row["expected_match_token_indices"], [0, 1, 2, 3, 4])
        self.assertEqual(row["non_matchable_token_indices"], [])

    def test_replace_block_mixes_stem_and_synonym_pairing(self):
        # Padded to clear the tokenizer's 5-token minimum. difflib reports
        # "eski qadimgi" (2 source words) / "eskirgan zamonaviy" (2 query
        # words) as a single "replace" opcode of EQUAL length -- paired
        # index-by-index: index0 "eski"/"eskirgan" shares a stem (prefix
        # "eski"); index1 "qadimgi"/"zamonaviy" does not.
        source = "eski qadimgi shahar katta bozor"
        query = "eskirgan zamonaviy shahar katta bozor"
        row = mms.token_level_ground_truth(query, source)
        # Query tokens: eskirgan(0) zamonaviy(1) shahar(2) katta(3) bozor(4).
        self.assertEqual(row["counts"], {"equal": 3, "replace_stem": 1, "replace_synonym": 1, "inserted": 0})
        self.assertEqual(row["expected_match_token_indices"], [0, 2, 3, 4])
        self.assertEqual(row["non_matchable_token_indices"], [1])

    def test_every_index_classified_exactly_once(self):
        # Invariant: expected + non_matchable must partition
        # range(query_token_count) with no gaps or overlaps, for any input,
        # since difflib's opcodes partition the query sequence completely.
        cases = [
            ("katta oq uy juda yaxshi", "katta oq uy juda yaxshi"),
            ("u katta falsafalari haqida yozdi", "u katta falsafasi haqida yozdi"),
            ("katta shahar eski markazida bozor ochildi", "katta shahar markazida bozor ochildi"),
            ("katta shahar markazida bozor ochildi", "katta shahar eski markazida bozor ochildi"),
        ]
        for query, source in cases:
            row = mms.token_level_ground_truth(query, source)
            combined = sorted(row["expected_match_token_indices"] + row["non_matchable_token_indices"])
            self.assertEqual(combined, list(range(row["query_token_count"])))


if __name__ == "__main__":
    unittest.main()
