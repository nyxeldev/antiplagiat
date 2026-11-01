# uz-latin-v3 — D1: ikki nuqsonni tuzatish

Versiya 1 · 2026-10-18 · Oldingi hisobot: [uz-morph-v3.md](uz-morph-v3.md) (C bosqichi, commit `f088feb`) · Kod: [backend/corpus.py](../../backend/corpus.py), [backend/comparison/uz_latin_v3.py](../../backend/comparison/uz_latin_v3.py)

Ikkita C bosqichida topilgan nuqson shu bosqichda tuzatildi. v2 yo'li, original matn, offset va highlight **o'zgarmadi** — bu quyida test bilan tasdiqlangan, da'vo bilan emas.

## D1.1 — Casefold assimetriyasi (C2)

**Qaror: so'rov tomonini tuzatish, indeks tomonini emas.**

Ikki variant bor edi: (a) indeks tomonini ham casefold qilib, ikkisini "kichik harf darajasida" tenglashtirish; (b) so'rov tomonini indeks kabi original katta-kichik harfga qaytarish. **(a) tanlanmadi**, chunki u bosh-harf-asosidagi atoqli-ot himoyasini IKKALA tomonda ham o'chirib qo'yardi (casefold qilingandan keyin hech qanday so'z "katta harfli" bo'lmaydi) — bu nuqsonni "tuzatish" o'rniga himoyani butunlay yo'q qilish bo'lardi. **(b) tanlandi**: `corpus.query_windows()` endi `normalization="v3"` bo'lganda yangi `text` argumentidan foydalanib, har bir tokenning ASL (katta-kichik harfli) ko'rinishini o'zining offset orqali original matndan oladi — xuddi indeks tomoni `chunk_text` bilan doim qilgani kabi.

**Kod o'zgarishi:** `backend/corpus.py` — `query_windows(tokens, normalization="v2", text=None)` va `candidates(..., text=None)`. `normalization="v3"` bo'lib, `text` berilmasa — `ValueError` (jim qolib noto'g'ri ishlashdan ko'ra ochiq xato). v2 yo'li (`text=None`, standart) **birorta qatorga ham tegmadi** — eski xatti-harakat aynan saqlangan (test bilan tasdiqlangan, pastda).

**Atoqli ot/qisqartma himoyasi ikkala tomonda ham ishlaydi:** endi ikkala tomon ham bir xil `uz_latin_v3._looks_non_uzbek()` funksiyasiga original katta-kichik harfli so'zni beradi — kod darajasida bir xil funksiya, bir xil kirish.

### O'lchov: mos kelmaslik ulushi

| | Oldin (C2) | Keyin (D1.1) |
| --- | --- | --- |
| O'zbekcha tokenlar orasida index/query mos kelmasligi | **222/11695 (1.90%)** | **0/11695 (0.00%)** |

Konkret misol (`Alisher Navoiyning ijodi ... kotarildi.`):

```
INDEKS tomoni (o'zgarmadi):  '... Navoiyning ijodi ... daraja kotaril.'
SO'ROV tomoni — OLDIN:      '... navoiy ijodi ... daraja kotaril'      <- "navoiy"ga qirqilgan
SO'ROV tomoni — KEYIN:      '... Navoiyning ijodi ... daraja kotaril'  <- endi indeks bilan bir xil
```

### Original matn/offset/highlight o'zgarmaganligi

Mavjud integratsion testlar (`backend/tests/test_corpus_integration.py`) qayta ishga tushirildi — ularning ikkisi aynan shu kafolatni tekshiradi:
- `test_v3_column_is_populated_without_changing_original_text_or_offsets` — `extracted_text`, `segments`, har chunkning `char_start/char_end` orqali olingan original matn o'zgarmaganini haqiqiy bazada tekshiradi.
- `test_v3_retrieval_never_changes_what_the_comparison_highlights` — `compare()` natijasidagi moslik oralig'lari `normalization="v2"` va `"v3"` orasida AYNAN bir xil ekanligini tasdiqlaydi (endi `text=` parametri bilan yangilangan).

### Regressiya testi (yangi, aynan shu nuqson qaytmasligi uchun)

`backend/tests/test_uz_latin_v3.py::IndexQuerySymmetryRegressionTests` (3 test):
- `test_query_side_requires_text_for_v3` — `text=` berilmasa `ValueError` kutiladi (jim noto'g'ri ishlash emas).
- `test_index_and_query_side_stem_a_capitalised_word_identically` — yuqoridagi "Navoiyning" misolini so'z darajasida solishtiradi va atoqli ot himoyasining ikkala tomonda HAQIQATAN ishlaganini tekshiradi (vacuous bo'lmasligi uchun `assertIn` bilan).
- `test_v2_query_windows_is_unaffected_by_the_new_text_parameter` — v2 yo'li yangi parametrdan mustaqil ekanligini tasdiqlaydi.

## D1.2 — Chet so'zlarni noto'g'ri qirqish

**Ikki variant baholandi:**

**(a) `corpus_documents.language_hint`'dan foydalanish.** Korpus tomonida ishonchli (metama'lumot aniq), lekin ikki jiddiy kamchilik bilan: **(1)** granularity butun HUJJAT darajasida — `language_hint="uz"` bo'lgan hujjat ichida "workshop'lar", "CRISPR-Cas9" kabi key chet so'zlar bo'lishi mumkin (aynan C1.4'da topilgan holat!), ya'ni bu usul hujjat ICHIDAGI aralash so'zlarni umuman tutmaydi; **(2)** so'rov tomonida bunday metama'lumot yo'q — tekshiriluvchi hujjat yuklanganda til belgisi saqlanmaydi, demak qandaydir fallback ("har doim 'uz' deb hisobla") kerak bo'lardi, bu esa D1.1'da aynan tuzatilgan index/query assimetriyasining YANGI shaklini yaratardi (indeks tomoni til bo'yicha filtrlaydi, so'rov tomoni filtrlay olmaydi).

**(b) Token-asosli tekshiruv (TANLANDI).** O'zbek lotin alifbosida standalone **"c"** harfi umuman yo'q — faqat "ch" juftligi tarkibida bo'ladi (ilmiy qarz so'zlar "molekula", "stsenariy" kabi "k"/"s" bilan yoziladi, "c" bilan emas); **"w"** ham yo'q (/v/ tovushi doim "v"). Bu — alifbo haqidagi FAKT, lug'at emas, va ikkala tomonda (index/query) bir xil `_looks_non_uzbek()` orqali ishlaydi, demak D1.1'dagi kabi yangi assimetriya yaratmaydi.

**Sabab bilan tanlov:** (b) granularity so'z darajasida to'g'ri keladi va so'rov tomonida HAM ishlaydi (metama'lumotga bog'liq emas) — (a)ning ikkala kamchiligini oldini oladi.

**Implementatsiya:** `backend/comparison/uz_latin_v3.py`, `_looks_non_uzbek()`:
```python
lowered = word.lower()
return "w" in lowered or "c" in lowered.replace("ch", "")
```
(bosh harf/raqam tekshiruvi bilan birga, `or` orqali).

### O'lchov: noto'g'ri qirqilgan chet so'zlar soni

| | Oldin (C1.4) | Keyin (D1.2) |
| --- | --- | --- |
| en/ru noto'g'ri stem qilingan tokenlar | **15** | **11** (−27%) |

Tuzatilgan misollar (endi himoyalangan): `molecular`→`molecular` (edi `molecu`), `screening`→`screening` (edi `scree`).

**Qolgan 11 ta hammasi "-ing" shaklida** (`learning`×9, `planning`×1, `threatening`×1) — bu ATAYLAB qoldirildi. Sabab: "-ing" bilan tugaydigan so'zni umuman bloklash o'zbekning O'ZINING siylov buyruq shakli bilan to'qnashadi — "tushuning" (tushunib qo'ying), "keling", "o'qing" kabi so'zlar ham "-ing" bilan tugaydi va bular haqiqiy, keng tarqalgan o'zbekcha so'zlar. Rasmiy ilmiy matnda (BMI, dissertatsiya) buyruq mayli juda kam uchraydi, lekin bu to'qnashuv nazariy jihatdan haqiqiy bo'lgani uchun qo'shilmadi — "molecular"/"screening"ni tuzatish narxi aniq va past (false-negative'siz), "-ing"ni butunlay bloklash narxi noaniq va potentsial yuqori.

### Testlar (yangi, 5 ta)

`backend/tests/test_uz_latin_v3.py::StemSafetyTests` ga qo'shildi: `test_bare_c_not_in_a_ch_digraph_marks_a_word_as_foreign` ("molecular"), `test_w_marks_a_word_as_foreign` ("workshoplarni"), `test_ch_digraph_is_not_mistaken_for_a_bare_c` ("chaqiriqlarni" — himoya haqiqiy "ch"ni chet so'z deb hisoblamasligi kerak), `test_native_word_with_ch_and_a_long_suffix_chain_still_strips` ("kuchlarning"), `test_guard_is_language_agnostic_any_bare_c_or_w_is_caught` (rus tilidan norasmiy transliteratsiya misoli).

## D1.3 — C3'ni qayta o'lchash (ikkala tuzatishdan keyin)

`--repeat 2` bilan determinizm qayta tasdiqlandi. To'liq jadval: [uz-morph-v3-retrieval-delta.csv](uz-morph-v3-retrieval-delta.csv) (yangilangan — ESKI raqamlar pastda saqlangan, tarixiy nusxa: commit `f088feb`dagi fayl).

| Qatlam | v2 (o'zgarmadi) | v3 — C bosqichi (tuzatishdan OLDIN) | v3 — D1 (tuzatishdan KEYIN) |
| --- | --- | --- | --- |
| **Morfologik YUQORI (≥35%, n=5)** recall@1 | 0.4000 | 0.4000 | **0.6000** |
| recall@5 / @10 | 0.8000 | 1.0000 | 1.0000 |
| MRR | 0.5067 | 0.6067 | **0.7067** |
| **Morfologik PAST (<20%, n=10)** recall@1/@5/@10/MRR | 1.0000 (barchasi) | 1.0000 (barchasi, o'zgarmadi) | 1.0000 (barchasi, o'zgarmadi) |
| **paraphrase (n=15)** recall@1 | 0.4667 | 0.5333 | **0.6000** |
| MRR | 0.5800 | 0.6133 | **0.6389** |
| **BARCHASI (n=53... recall@1 hisoblangan so'rovlar)** recall@1 | 0.6604 | 0.6792 | **0.7170** |
| MRR | 0.7204 | 0.7393 | **0.7575** |

**Kutilmagan, lekin mantiqiy natija: tuzatish FOYDANI PASAYTIRMADI, OSHIRDI.** Buning sababi — tuzatishdan oldin so'rov tomoni indeksga qaraganda KO'PROQ (nazoratsiz) stem qilardi, chunki bosh harf himoyasi so'rov tomonida umuman ishlamasdi. Bu "ko'proq stemlash" ba'zan tasodifan recall'ni oshirardi, lekin indeks bilan IZCHIL emas edi (C2'dagi "Navoiyning" misoli — mos kelmaslik). Tuzatilgandan keyin ikki tomon ANIQ bir xil leksemalarni hosil qiladi, bu esa aynan "katta harfli ism + qo'shimcha" naqshiga ega matnlar (o'zbek ilmiy matnida juda keng tarqalgan — "Navoiyning", "Olimlar", "Davlat" kabi) uchun to'g'ri, izchil moslikni beradi — tasodifiy emas, tizimli foyda.

## Darvoza

170 backend testi (162 + 8 yangi: 3 simmetriya regressiyasi + 5 chet-so'z himoyasi). Determinizm `--repeat 2` bilan tasdiqlandi. Migratsiya qo'shilmadi (D1 faqat Python darajasidagi funksiya, yangi ustun/jadval kerak emas). Push yo'q.
