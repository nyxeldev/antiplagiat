# uz-latin-v3 matching bosqichiga kengaytirildi — uch rejim o'lchovi

Versiya 1 · 2026-11-03 · Kod: [backend/comparison/matching.py](../../backend/comparison/matching.py) (`compare(matching_normalization=...)`, `match_keys()`, `morph_key()`) · Harness: [scripts/eval_retrieval.py](../../scripts/eval_retrieval.py) (`ablation_uz_latin_v3`, `ablation_uz_latin_v3_matching`) · Nazorat to'plami: [benchmarks/corpus-v2/](../../benchmarks/corpus-v2/) · Xom ma'lumot: [raw.csv](../../benchmarks/corpus-v2/results/raw.csv), [summary.json](../../benchmarks/corpus-v2/results/summary.json)

**MAJBURIY OGOHLANTIRISH.** Raqamlar **sintetik, 59 hujjatli/67 so'rovli nazorat to'plamidan** (`benchmarks/corpus-v2/`); haqiqiy BMI matnlarida sifatning isboti emas. O'xshashlik foizi plagiatning avtomatik isboti emas. Bu hujjat [docs/decisions.md §5](../decisions.md)dagi uch-rejim modelini amalga oshirgandan keyingi o'lchov; oldingi (retrieval-only) bosqich uchun [uz-morph-v3.md](uz-morph-v3.md)ga qarang.

## 0. Qisqa xulosa

| Savol | Javob |
| --- | --- |
| Matching recall ko'tarildimi? | **Ha, sezilarli.** Morfologik so'rovlarning ENG QIYIN qatlamida (suffix% >= 35%) matching recall 0.1802 -> **0.5238** (+0.3436). Past qatlamda (suffix% < 20%) 0.7234 -> **0.8545** (+0.1311). |
| Precision qancha tushdi? | **Tushmadi — 1.0da qoldi har bir rejim, har bir qatlamda**, shu jumladan `hard_negative`+`unrelated` (n=14, yolg'on musbat soni 0, uch rejimning hech birida). |
| Offset/highlight kafolati buzildimi? | **Yo'q.** Har bir topilgan moslik hamon to'liq original so'zni (qo'shimchasi bilan) qamraydi — `backend/comparison/matching.py`dagi `span()` o'zgarmagan, faqat shingle tenglik tekshiruvi (`morph_key()`) yangi. Isbotlangan testlar: §3. |
| Eski so'rovlar (off/retrieval) o'zgardimi? | **Yo'q, bit-ma-bit bir xil.** `normalization="v2"`/`"v3"` default `matching_normalization="uz-latin-v2"` bilan chaqiriladi — `compare()`ning parametrsiz chaqiruvi bilan aynan bir xil natija. |
| Determinizm? | `--repeat 2` bilan tasdiqlangan: ikki pass CSV'si (timing ustunlaridan tashqari) bit-ma-bit bir xil. |

## 1. Uch rejim, yonma-yon (umumiy, 67 so'rov)

| Rejim | `normalization` | retrieval recall@1 | recall@5/@10 | MRR | matching precision | matching recall | matching F1 | FP so'rovlar (hard_negative+unrelated, n=14) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| off | `v2` | 0.6604 | 0.8302 | 0.7204 | 1.0000 | 0.6163 | 0.6424 | 0 |
| retrieval | `v3` | 0.7170 | 0.8491 | 0.7575 | 1.0000 | 0.6177 | 0.6448 | 0 |
| retrieval+matching | `v3-matching` | 0.7170 | 0.8491 | 0.7575 | 1.0000 | **0.6615** | **0.6848** | 0 |

Retrieval ustunlari `retrieval`/`retrieval+matching` orasida bir xil — kutilganidek, chunki ikkisi ham xuddi bir xil `fts_v3` nomzod tanlashdan foydalanadi (§ decisions.md §5 jadvali); farq faqat matching ustunlarida.

## 2. Morfologik so'rovlar, suffix% qatlami bo'yicha (n=15, ikki qatlamga bo'lingan)

Qatlamlash manbasi: `benchmarks/corpus-v2/morph_strength.json`dagi `suffix_changed_ratio` (har bir morfologik so'rov uchun `scripts/measure_morph_strength.py` bilan oldindan hisoblangan). Yuqori qatlam (>= 35%) n=5, past qatlam (< 20%) n=10; oraliqda (20–35%) hech bir so'rov yo'q (toza ikkiga bo'linish).

| Qatlam | Rejim | matching precision | matching recall | matching F1 | FP tokenlar |
| --- | --- | --- | --- | --- | --- |
| suffix% >= 35% (n=5) | off | 1.0000 | 0.1802 | 0.2719 | 0 |
| | retrieval | 1.0000 | 0.1982 | 0.3048 | 0 |
| | **retrieval+matching** | **1.0000** | **0.5238** | **0.6749** | **0** |
| suffix% < 20% (n=10) | off | 1.0000 | 0.7234 | 0.8379 | 0 |
| | retrieval | 1.0000 | 0.7234 | 0.8379 | 0 |
| | **retrieval+matching** | **1.0000** | **0.8545** | **0.9205** | **0** |

**O'qilishi:** foyda aniq bir qatlamga tegishli, xuddi retrieval darajasidagi avvalgi o'lchov (uz-morph-v3.md §3) kabi — ENG QIYIN qatlamda (ko'p qo'shimcha o'zgargan so'rovlar) matching recall deyarli 3x ko'tariladi (0.18 -> 0.52), past qatlamda ham haqiqiy, lekin kichikroq foyda (0.72 -> 0.85). Ikkala qatlamda ham precision 1.0da qoladi — bu nazorat to'plamida stemming kolliziyasi (turli so'zlarning bitta o'zakka tushib, yolg'on moslik yaratishi) kuzatilmadi.

## 3. Offset/highlight kafolati — testlar, da'vo emas

Qabul mezoni "Mos parcha normallashtirilgan fazoda topiladi, lekin foydalanuvchiga ORIGINAL matndagi TO'LIQ so'z belgilanishi shart" quyidagi testlar bilan isbotlangan (ikkisi ham `--repeat`siz, bitta aniq lokal yurgizishda o'tadi, Postgres fixture'siz birinchisi, fixture bilan ikkinchisi):

- `backend/tests/test_comparison.py::MatchingTests::test_v3_matching_finds_morphological_variants_v2_misses` — olti so'zli sun'iy jumla, har bir so'z faqat qo'shimchasi bilan farq qiladi (`kitoblarni`/`kitoblardan` va h.k.). v2 bilan `matched_tokens=0`; `matching_normalization="uz-latin-v3"` bilan `matched_tokens=6`, va highlight matni (`match["document"]["text"]`) hujjatning TO'LIQ matniga teng — qisqartirilgan o'zakka emas.
- `backend/tests/test_comparison.py::MatchingTests::test_v3_matching_does_not_merge_unrelated_words_into_one_stem` — bog'liq bo'lmagan so'zlar (`test_uz_latin_v3.py`dagi kolliziya-xavfsizlik so'zlaridan) v3-matching bilan ham mos deb belgilanmaydi.
- `backend/tests/test_corpus_integration.py::CorpusComparisonTests::test_v3_matching_finds_what_v3_retrieval_only_misses` — to'liq API (`POST /compare?include_corpus=true&normalization=v3-matching`) orqali, haqiqiy (disposable) PostgreSQL ustida: `normalization="v3"` bilan korpus nomzodi topiladi, lekin `matches=[]` (v2 matching suffix farqini ko'rmaydi); `normalization="v3-matching"` bilan xuddi shu nomzod endi `matches` bilan qaytadi, va highlight matni CHECKED tomonning TO'LIQ original so'zlarini (o'z qo'shimchasi bilan) qamraydi.

Mavjud v2 offset testlari (`test_unicode_apostrophes_whitespace_and_original_coordinates`, `test_invisible_highlight_with_prefix_and_suffix`, `test_v3_retrieval_never_changes_what_the_comparison_highlights` va h.k.) o'zgarishsiz o'tadi (§4).

## 4. Darvoza

183 backend testi (178 + 5 yangi: `test_matching_normalization_defaults_to_v2_unchanged`, `test_matching_normalization_rejects_unknown_value`, `test_v3_matching_finds_morphological_variants_v2_misses`, `test_v3_matching_does_not_merge_unrelated_words_into_one_stem`, `test_v3_matching_finds_what_v3_retrieval_only_misses`), barchasi o'tadi. `off` rejimida (parametrsiz `compare()` chaqiruvi) natijalar bit-ma-bit o'zgarmagan — buni `test_matching_normalization_defaults_to_v2_unchanged` va qolgan 178 testning o'zgarishsiz o'tishi tasdiqlaydi. Determinizm `scripts/eval_retrieval.py --corpus corpus-v2 --repeat 2` bilan tasdiqlandi.

## 5. Tekshirilmagan qolgan narsalar

- **Frontend UI'da rejim tanlash yo'q.** `frontend/app/comparison.tsx`dagi mavjud "tajriba" belgisi hamon faqat `normalization=v3` (retrieval) yuboradi; `v3-matching` hozircha faqat to'g'ridan-to'g'ri API chaqiruvi orqali (yoki `scripts/eval_retrieval.py`/testlar orqali) yetib boriladi — xuddi "v3" o'zi ham avval shunday boshlangani kabi. Bu vazifaning sanab o'tilgan band(lar)ida (1–6) frontend o'zgarishi so'ralmagan edi.
- **Haqiqiy BMI matnlarida tasdiqlanmagan.** Barcha raqamlar 59/67 hajmli sintetik nazorat to'plamidan (`benchmarks/corpus-v2/`); real foydalanuvchi hujjatlarida yolg'on musbat xavfi bu yerda kuzatilgan 0dan farqli bo'lishi mumkin.
- **`MIN_WORD_LEN_TO_STRIP`/`MIN_STEM_LEN` qayta sozlanmadi.** `backend/comparison/uz_latin_v3.py`dagi xavfsizlik chegaralari (7/4 belgi) o'zgarishsiz qoldi; bu o'lchov ularning matching darajasidagi tarqalishini (shunday chegaralar bilan) tasdiqladi, lekin ularni qattiqlashtirish/yumshatishni tekshirmadi.
- **`paraphrase`/`partial`/`quoted`/`verbatim` kategoriyalari bu hujjatda alohida qatlamlanmagan** — ular suffix_changed_ratio bilan hisoblanmaydi (faqat `morphological` toifasi uchun hisoblangan, `scripts/measure_morph_strength.py`ning o'z qamrovi bo'yicha); umumiy (barcha toifalar) raqam §1da bor.
