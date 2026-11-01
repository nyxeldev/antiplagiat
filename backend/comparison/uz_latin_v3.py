"""uz-latin-v3: a rule-based, dictionary-free suffix-stripping policy for the
RETRIEVAL/INDEX side only.

Scope boundary (do not weaken without re-reading docs/architecture.md):
  - This module never touches `extracted_text`, `segments`, token offsets or
    anything shown to a reader. It only produces a retrieval-only surrogate
    string that feeds a separate tsvector column (`corpus_chunks.fts_v3`).
  - uz-latin-v2 (backend/comparison/matching.py, NORMALIZATION_VERSION) is
    unchanged and stays the default everywhere. v3 is opt-in per call
    (backend/corpus.py candidates(..., normalization="v3")).
  - No lexicon, no stemming dictionary, no ML model. Every rule below is a
    plain Uzbek Latin suffix string plus the grammatical role it spells out,
    so a reviewer can check each one against a grammar reference without
    needing test data.

Why "lightweight": Uzbek stacks suffixes (noun + plural + case, e.g.
"kitob-lar-da"). Rather than encode every stacked combination, stem() strips
at most MAX_PASSES single morphemes, longest match first each pass, which
unwinds common two-suffix stacks (case then plural) without a combinatorial
rule table.
"""
import re

NORMALIZATION_VERSION_V3 = "uz-latin-v3"

# --- safety: "qisqa so'zlarga tegmaslik" -----------------------------------
# Words at or below this length are returned unchanged. This alone keeps most
# short borrowed technical terms (test, sayt, link, chart, ...) and short
# native words out of reach of any suffix rule below.
MIN_WORD_LEN_TO_STRIP = 7

# --- safety: "o'zak minimal uzunligi" --------------------------------------
# A strip is only applied if the remaining stem is still at least this long.
# Combined with MIN_WORD_LEN_TO_STRIP, this bounds how much of a short word
# a single rule can ever remove.
MIN_STEM_LEN = 4

# A word is stripped at most this many times (longest-matching suffix first
# each pass), e.g. "kitoblarda" -> strip "da" -> "kitoblar" -> strip "lar" ->
# "kitob". Kept small on purpose: more passes mean more chances to compound
# a borderline-safe single strip into an unsafe one.
MAX_PASSES = 2

# Ordered here by grammatical category for readability; stem() always tries
# the LONGEST matching suffix first regardless of this order (see
# _SUFFIXES_BY_LENGTH below), so listing order here never affects behaviour.
# Deliberately excluded: bare "-i" (3rd person possessive) and bare "-li"/
# "-siz" (relational/privative) -- all three are a single short vowel or two
# common letters away from being "just how the word ends" for a lot of
# unrelated native and borrowed words, which is exactly the "ikki boshqa
# so'z bir o'zakka tushib qolmasligi" risk the rule set is meant to avoid.
SUFFIXES = (
    # case suffixes
    ("ning", "genitive (-ning)"),
    ("gacha", "terminative case (-gacha, 'up to/until')"),
    ("ni", "accusative (-ni)"),
    ("dan", "ablative (-dan)"),
    ("tan", "ablative, voiceless-stem allomorph (-tan)"),
    ("ga", "dative (-ga)"),
    ("qa", "dative, velar-stem allomorph (-qa)"),
    ("ka", "dative, voiceless-stem allomorph (-ka)"),
    ("dagi", "locative-adjectival (-dagi, 'the one in/at')"),
    ("da", "locative (-da)"),
    ("ta", "locative, voiceless-stem allomorph (-ta)"),
    # plural + 3rd person possessive-plural
    ("lar", "plural (-lar)"),
    ("lari", "plural + 3rd person possessive (-lari)"),
    ("si", "3rd person possessive, vowel-stem allomorph (-si)"),
    # verb suffixes most likely to appear as the final, inflected form
    ("moqda", "present continuous (-moqda)"),
    ("gan", "perfect participle (-gan)"),
    ("adi", "aorist, 3rd person (-adi)"),
    ("ydi", "aorist, vowel-stem allomorph (-ydi)"),
    ("di", "past definite (-di)"),
    ("ti", "past definite, voiceless-stem allomorph (-ti)"),
)
# Known, accepted imprecision: "-adi" (aorist, e.g. "kel-adi") and a
# vowel-final stem's own last letter "a" plus "-di" (past, e.g.
# "tasdiqla-di") can end in the same four letters. Longest-match-first picks
# "-adi" either way, so e.g. "tasdiqladi" stems to "tasdiql" rather than the
# grammatically cleaner "tasdiqla". This never merges two unrelated roots
# (verified in test_uz_latin_v3.py's collision tests) -- it just sometimes
# leaves one extra or one missing trailing letter on a verb stem, which the
# GIN/tsvector index still matches consistently across that verb's own forms.

# Longest suffix first, so "-lari" is tried before "-lar" and "-dagi" before
# "-da"; a shorter suffix that is a substring of a longer one never wins by
# accident of list order.
_SUFFIXES_BY_LENGTH = tuple(sorted(SUFFIXES, key=lambda pair: -len(pair[0])))

_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)


def _looks_non_uzbek(word):
    """Heuristic proxy for "rus/ingliz so'zini kesmaslik" -- no dictionary.

    Two independent signals, neither a lexicon lookup:

    1. Embedded untranslated foreign terms and acronyms in Uzbek Latin text
       (COVID-19, CRISPR-Cas9, ATP, DNK, Coursera, edX, ...) are, in
       practice, either all-uppercase, contain a digit, or are capitalised
       mid-sentence (a proper noun). A plain lowercase Uzbek word matches
       none of these, so this costs some recall on capitalised common nouns
       at a sentence start but never strips a suffix-shaped ending off an
       acronym or a name.

    2. A Latin-orthography fact about Uzbek itself, not about any other
       language: Uzbek Latin spelling has no standalone "c" letter -- its
       "c" sound is always spelled "ch" (kuch, chaqiriq); a loanword that in
       English/Russian would use "c" is respelled with "s" or "k" in Uzbek
       (molekula, stsenariy, kafe), never "c". Likewise Uzbek has no "w" --
       its /v/ sound is always "v". So a bare "c" that is not part of a
       "ch" digraph, or any "w", can only appear in a word carried over
       verbatim from another Latin-script language, never in native Uzbek
       spelling. This is what catches "molecular" (measured in
       docs/benchmarks/uz-morph-v3.md, C1.4); it does NOT catch English
       words shaped like "learning"/"planning" that contain neither letter
       -- see docs/benchmarks/uz-morph-v3-foreign-guard.md for why a
       suffix-shape check for those was deliberately left out (it collides
       with Uzbek's own "-ing" polite imperative, e.g. "tushuning").
    """
    if any(ch.isdigit() for ch in word) or word[:1].isupper():
        return True
    lowered = word.lower()
    return "w" in lowered or "c" in lowered.replace("ch", "")


def _strip_once(word):
    # No length gate here: the one-time whole-word gate in stem() already
    # decided this word is long enough to bother with. Checking only
    # MIN_STEM_LEN here means a longer suffix that gets rejected for leaving
    # too short a stem does NOT fall through to a shorter suffix that
    # happens to be its own tail (e.g. "-moqda" rejected must not fall back
    # to the unrelated "-da" sitting inside it) -- the outer loop already
    # tries longest-first, so the first accepted match is final for this pass.
    for suffix, _role in _SUFFIXES_BY_LENGTH:
        if not word.endswith(suffix):
            continue
        stem = word[: -len(suffix)]
        return stem if len(stem) >= MIN_STEM_LEN else word
    return word


def _strip_tail(tail):
    for _ in range(MAX_PASSES):
        stripped = _strip_once(tail)
        if stripped == tail:
            break
        tail = stripped
    return tail


def stem(word):
    """Strip at most MAX_PASSES Uzbek suffixes from one already-tokenized word.

    An apostrophe inside the word is treated as an ordinary letter, not a
    boundary to special-case: in Uzbek Latin orthography it is most often
    part of the letters o'/g' (to'g'ri, bo'lmoqda, qo'ygan, ...), so treating
    it as "foreign stem before, suffix after" would block stripping on a lot
    of entirely native words. The rare opposite case -- a bare borrowed word
    plus an Uzbek suffix written as e.g. "workshop'lar" -- still comes out
    reasonably (the match is against the literal tail "...'lar", so the
    stripped result keeps the trailing apostrophe, e.g. "workshop'"), just
    without a dedicated rule to clean that trailing mark up.
    """
    if _looks_non_uzbek(word):
        return word
    if len(word) <= MIN_WORD_LEN_TO_STRIP:
        return word
    return _strip_tail(word)


def stem_text(text):
    """Retrieval-only surrogate of `text`: every word replaced by stem(word).

    Non-word characters (whitespace, punctuation, digits-as-their-own-tokens)
    pass through untouched, so this is safe to run over an entire chunk of
    text and feed straight into to_tsvector(); it never changes which
    characters are word boundaries, only what sits inside each one.
    """
    return _WORD.sub(lambda m: stem(m.group()), text)
