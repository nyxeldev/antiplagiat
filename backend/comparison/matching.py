"""Explainable five-token shingles, expanded into contiguous matching runs."""
import re
import unicodedata
from collections import defaultdict

from .policy import ComparisonError, MAX_MATCHES, MAX_OPERATIONS, MAX_TOKENS, SHINGLE_SIZE

APOSTROPHES = str.maketrans({c: "'" for c in "‘’ʻʼʹ`´＇"})
TOKEN = re.compile(r"[^\W_]+(?:'[^\W_]+)*", re.UNICODE)
INVISIBLE_RUN = re.compile(r"[\u200b\u00ad\u200c\ufeff]+")
NORMALIZATION_VERSION = "uz-latin-v2"
INVISIBLE_WARNING = "Lotin harflari orasidagi ko‘rinmas belgilar solishtirishda normallashtirildi; original matn saqlandi. ZWSP haqiqiy so‘z chegarasi ham bo‘lishi mumkin."
ARABIC_WARNING = "Arab harakatlari bo‘yicha tokenizatsiya hali ishonchli emas; moslik va umumiy ko‘rsatkich ehtiyotkor talqin qilinishi kerak."


def latin_letter(char):
    return unicodedata.category(char).startswith("L") and "LATIN" in unicodedata.name(char, "")


def ignored_invisibles(text):
    # Only the explicit set, in runs immediately flanked by Latin letters.
    # Other scripts' join controls, marks and real word boundaries stay intact.
    return {i for run in INVISIBLE_RUN.finditer(text)
            if run.start() > 0 and run.end() < len(text)
            and latin_letter(text[run.start() - 1]) and latin_letter(text[run.end()])
            for i in range(run.start(), run.end())}


def has_arabic_marks(text):
    return any(unicodedata.category(c).startswith("M")
               and "ARABIC" in unicodedata.name(c, "") for c in text)


def tokenize(text):
    normalized, offsets = [], []
    ignored = ignored_invisibles(text)
    # Keep a map through NFKC composition and casefold expansions (e.g. ß).
    for group in re.finditer(r".[\u0300-\u036f]*", text, re.DOTALL):
        retained = "".join(c for i, c in enumerate(group.group(), group.start()) if i not in ignored)
        value = unicodedata.normalize("NFKC", retained).translate(APOSTROPHES).casefold()
        normalized.append(value)
        offsets.extend([(group.start(), group.end())] * len(value))
    tokens = [{"value": m.group(), "start": offsets[m.start()][0], "end": offsets[m.end() - 1][1]}
              for m in TOKEN.finditer("".join(normalized))]
    if not tokens:
        raise ComparisonError("empty", "Matnda solishtirish uchun so‘zlar topilmadi.")
    if len(tokens) < SHINGLE_SIZE:
        raise ComparisonError("too_short", "Har bir hujjatda kamida 5 ta token (so‘z/son) bo‘lishi kerak.")
    if len(tokens) > MAX_TOKENS:
        raise ComparisonError("token_limit", "Bitta hujjat 30 000 tokendan oshmasligi kerak.")
    return tokens


def span(document, tokens, start, end):
    left, right = tokens[start]["start"], tokens[end - 1]["end"]
    places = [s for s in document["segments"] if s["start"] < right and s["end"] > left]
    return {"start": left, "end": right, "token_start": start, "token_end": end,
            "text": document["text"][left:right],
            "location": {"kind": places[0]["kind"], "from": places[0]["number"], "to": places[-1]["number"]}}


def runs(target, source):
    a, b = [t["value"] for t in target], [t["value"] for t in source]
    if a == b:
        return [(0, 0, len(a))]
    index = defaultdict(list)
    n = SHINGLE_SIZE
    for j in range(len(b) - n + 1):
        index[tuple(b[j:j + n])].append(j)
    found, diagonals, operations = [], {}, 0
    for i in range(len(a) - n + 1):
        for j in index.get(tuple(a[i:i + n]), ()):
            operations += 1
            if operations > MAX_OPERATIONS:
                raise ComparisonError("comparison_limit", "Takroriy matnlar solishtirish chegarasidan oshdi. Kichikroq hujjat tanlang.")
            if diagonals.get(j - i, -1) >= i + n:
                continue
            length = n
            while i + length < len(a) and j + length < len(b) and a[i + length] == b[j + length]:
                length += 1
                operations += 1
                if operations > MAX_OPERATIONS:
                    raise ComparisonError("comparison_limit", "Solishtirish amallari chegarasidan oshdi.")
            diagonals[j - i] = i + length
            found.append((i, j, length))
            if len(found) > MAX_MATCHES:
                raise ComparisonError("match_limit", "Bir manbada 500 dan ortiq mos parcha. Hujjatni kichraytiring.")
    return found


def compare(document, sources):
    all_docs = [document, *sources]
    warnings = []
    if any(ignored_invisibles(doc["text"]) for doc in all_docs):
        warnings.append(INVISIBLE_WARNING)
    if any(has_arabic_marks(doc["text"]) for doc in all_docs):
        warnings.append(ARABIC_WARNING)
    tokens = []
    for doc in all_docs:
        try:
            tokens.append(tokenize(doc["text"]))
        except ComparisonError as error:
            error.file = doc["name"]
            raise
    covered = set()
    results = []
    for number, (source, source_tokens) in enumerate(zip(sources, tokens[1:]), 1):
        local, matches = set(), []
        for i, j, length in runs(tokens[0], source_tokens):
            left = span(document, tokens[0], i, i + length)
            right = span(source, source_tokens, j, j + length)
            matches.append({"method": "exact" if left["text"] == right["text"] else "shingle",
                            "document": left, "source": right})
            local.update(range(i, i + length))
        covered.update(local)
        results.append({**source, "id": str(number), "token_count": len(source_tokens),
                        "coverage_percent": round(100 * len(local) / len(tokens[0]), 2),
                        "matched_tokens": len(local), "matches": matches})
    return {"status": "completed", "coverage_percent": round(100 * len(covered) / len(tokens[0]), 2),
            "matched_tokens": len(covered), "token_count": len(tokens[0]),
            "document": document, "sources": results,
            "parameters": {"shingle_size": SHINGLE_SIZE, "minimum_match_tokens": SHINGLE_SIZE,
                           "algorithm_version": "lexical-shingle-v1",
                           "normalization": "NFKC + casefold + apostrophe folding + Latin-internal U+200B/U+00AD/U+200C/U+FEFF runs",
                           "normalization_version": NORMALIZATION_VERSION,
                           "offset_unit": "Unicode code points; zero-based, end-exclusive"},
            "limitations": warnings + [
                "O‘xshashlik plagiatning avtomatik isboti emas.",
                "Natija faqat yuklangan manbalar doirasida; moslik yo‘qligi boshqa manbalarda yo‘qligini bildirmaydi.",
                "Iqtibos va bibliografiya filtri yo‘q; umumiy iboralar ham hisoblanadi.",
                "Bu leksik solishtirish: parafraz, ma’no yaqinligi va tarjima aniqlanmaydi.",
                "PDF o‘qish tartibi murakkab maketlarda buzilishi mumkin; OCR yo‘q. Matnsiz sahifali PDF rad etiladi.",
                "DOCXda asosiy matn va jadvallar olinadi; header/footer, izohlar, rasmlar va sahifa maketi tahlil qilinmaydi.",
                "TXTda bo‘sh bo‘lmagan har bir satr paragraf deb belgilanadi. 5 tokendan qisqa mosliklar hisoblanmaydi.",
            ]}
