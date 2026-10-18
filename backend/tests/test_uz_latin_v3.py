"""Unit tests for the uz-latin-v3 rule-based suffix stripper.

No database needed: every test here is a pure function call against
backend.comparison.uz_latin_v3. Integration tests proving the offset/
highlight invariant live in test_corpus_integration.py, since that needs a
real corpus_chunks row to check against.
"""
import unittest

from backend.comparison import uz_latin_v3 as v3


class StemPositiveTests(unittest.TestCase):
    """Each rule gets at least one word it is actually meant to strip."""

    def test_plural_lar(self):
        self.assertEqual(v3.stem("kitoblarni"), "kitob")  # -ni then -lar, two passes

    def test_genitive_ning(self):
        self.assertEqual(v3.stem("universitetning"), "universitet")

    def test_dative_ga(self):
        self.assertEqual(v3.stem("kitoblarga"), "kitob")

    def test_locative_da(self):
        self.assertEqual(v3.stem("maktablarda"), "maktab")

    def test_ablative_dan(self):
        self.assertEqual(v3.stem("shahardan"), "shahar")

    def test_terminative_gacha(self):
        self.assertEqual(v3.stem("kechgacha"), "kech")

    def test_locative_adjectival_dagi(self):
        self.assertEqual(v3.stem("maktabdagi"), "maktab")

    def test_present_continuous_moqda_on_a_long_enough_root(self):
        # "bo'l" (3 letters) + "-moqda" stays within MIN_STEM_LEN once the
        # apostrophe is counted as an ordinary letter of the root.
        self.assertEqual(v3.stem("bo'lmoqda"), "bo'l")

    def test_perfect_participle_gan(self):
        # tasdiq+la+n+gan: stripping "-gan" correctly leaves the passive
        # stem "tasdiqlan", not the bare verbalised root "tasdiqla".
        self.assertEqual(v3.stem("tasdiqlangan"), "tasdiqlan")

    def test_two_pass_strip_unwinds_case_then_plural(self):
        # "kitob" + "lar" + "da": outer case suffix first, then plural.
        self.assertEqual(v3.stem("kitoblarda"), "kitob")

    def test_two_pass_strip_unwinds_perfect_participle_then_terminative_like_chain(self):
        # "qo'y" (put) + "gan" + "da": outer locative first, then participle.
        self.assertEqual(v3.stem("qo'yganda"), "qo'y")


class StemSafetyTests(unittest.TestCase):
    """The guards named in the brief: short words, stem length, foreign words."""

    def test_word_at_the_length_threshold_is_untouched(self):
        word = "a" * v3.MIN_WORD_LEN_TO_STRIP
        self.assertEqual(v3.stem(word), word)

    def test_word_one_over_the_length_threshold_can_be_touched(self):
        word = "aaaa" + "gacha"  # 4-letter stem, 9 chars total, above threshold
        self.assertEqual(len(word), v3.MIN_WORD_LEN_TO_STRIP + 2)
        self.assertEqual(v3.stem(word), "aaaa")

    def test_short_word_is_never_touched_even_with_a_real_suffix_shape(self):
        # len("kelda") == 5 <= MIN_WORD_LEN_TO_STRIP(7): must pass through whole.
        self.assertEqual(v3.stem("kelda"), "kelda")

    def test_strip_refused_when_remaining_stem_would_be_too_short(self):
        # "aaa" (3 chars, below MIN_STEM_LEN(4)) + "gacha" -- long enough
        # overall to be considered, but the only matching suffix would leave
        # too short a stem, and there is no shorter suffix to fall back to.
        word = "aaa" + "gacha"
        self.assertEqual(v3.stem(word), word)

    def test_a_longer_suffix_rejected_for_stem_length_does_not_fall_back_to_a_shorter_one_inside_it(self):
        # "-moqda" on a 3-letter root ("kel") is rejected by MIN_STEM_LEN; the
        # word must stay whole, not fall back to stripping the unrelated
        # "-da" that happens to sit inside "-moqda".
        self.assertEqual(v3.stem("kelmoqda"), "kelmoqda")

    def test_capitalised_word_is_left_alone(self):
        # Proper noun heuristic: mid-sentence capital, no dictionary needed.
        self.assertEqual(v3.stem("Navoiyning"), "Navoiyning")

    def test_allcaps_acronym_is_left_alone(self):
        self.assertEqual(v3.stem("DNKlarning"), "DNKlarning")

    def test_word_with_a_digit_is_left_alone(self):
        self.assertEqual(v3.stem("COVID19ning"), "COVID19ning")

    def test_word_with_no_matching_suffix_is_unchanged(self):
        self.assertEqual(v3.stem("mamlakat"), "mamlakat")

    def test_bare_short_possessive_i_is_never_stripped(self):
        # Deliberately excluded suffix (see SUFFIXES comment): "kitobi" must
        # not become "kitob" by accident of some other rule either.
        self.assertEqual(v3.stem("kitobi"), "kitobi")

    def test_max_passes_bounds_how_many_suffixes_are_removed(self):
        # Three stackable suffixes ("dan"+"ning"+"lar"); a 3rd pass would
        # still find something to strip, but MAX_PASSES(2) stops it there.
        word = "aaaa" + "lar" + "ning" + "dan"
        after_two_passes = v3._strip_once(v3._strip_once(word))
        self.assertEqual(v3.stem(word), after_two_passes)
        self.assertNotEqual(after_two_passes, v3._strip_once(after_two_passes))


class StemCollisionTests(unittest.TestCase):
    """"Ikki boshqa so'z bir o'zakka tushib qolmasligi": curated word pairs
    with unrelated meanings must not collapse onto the same stem."""

    def test_bread_and_name_stay_distinct(self):
        self.assertNotEqual(v3.stem("nonlardan"), v3.stem("nomlardan"))

    def test_horse_and_grass_stay_distinct(self):
        self.assertNotEqual(v3.stem("otlarning"), v3.stem("o'tlarning"))

    def test_book_and_stone_stay_distinct(self):
        self.assertNotEqual(v3.stem("kitoblarga"), v3.stem("toshlarga"))

    def test_unrelated_short_words_are_both_left_alone_and_so_stay_distinct(self):
        # Below the strip threshold either way, so they trivially stay distinct.
        self.assertEqual(v3.stem("uyda"), "uyda")
        self.assertEqual(v3.stem("qayda"), "qayda")
        self.assertNotEqual(v3.stem("uyda"), v3.stem("qayda"))


class StemTextTests(unittest.TestCase):
    """stem_text() must only ever touch word characters, nothing else."""

    def test_punctuation_and_spacing_pass_through_untouched(self):
        text = "Kitoblarni, maktablarda — o'qing!"
        stemmed = v3.stem_text(text)
        self.assertEqual(stemmed, "Kitoblarni, maktab — o'qing!")
        # "Kitoblarni" (capitalised, sentence start) is left alone by the
        # proper-noun heuristic; "maktablarda" is not capitalised and strips.

    def test_each_word_is_independently_stemmed(self):
        text = "universitetning kitoblarini"
        self.assertEqual(v3.stem_text(text), "universitet kitob")

    def test_stem_text_never_changes_length_of_untouched_short_text(self):
        text = "A, B.  C!"
        self.assertEqual(v3.stem_text(text), text)  # too short to strip, punctuation untouched


if __name__ == "__main__":
    unittest.main()
