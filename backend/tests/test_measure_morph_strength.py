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


if __name__ == "__main__":
    unittest.main()
