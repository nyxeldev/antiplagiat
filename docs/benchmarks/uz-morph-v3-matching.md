# uz-latin-v3 matching bosqichiga kengaytirildi — uch rejim o'lchovi

Versiya 3 · 2026-11-04 · Kod: [backend/comparison/matching.py](../../backend/comparison/matching.py) (`compare(matching_normalization=...)`, `match_keys()`, `morph_key()`) · Harness: [scripts/eval_retrieval.py](../../scripts/eval_retrieval.py) (`ablation_uz_latin_v3`, `ablation_uz_latin_v3_matching`), [scripts/measure_morph_strength.py](../../scripts/measure_morph_strength.py) (`token_level_ground_truth()`), [scripts/measure_morph_token_precision.py](../../scripts/measure_morph_token_precision.py) · Nazorat to'plami: [benchmarks/corpus-v2/](../../benchmarks/corpus-v2/) · Xom ma'lumot: [raw.csv](../../benchmarks/corpus-v2/results/raw.csv), [summary.json](../../benchmarks/corpus-v2/results/summary.json), [morph_strength.json](../../benchmarks/corpus-v2/morph_strength.json), [morph_token_precision.json](../../benchmarks/corpus-v2/results/morph_token_precision.json)

**MAJBURIY OGOHLANTIRISH.** Raqamlar **sintetik, 59 hujjatli/67 so'rovli nazorat to'plamidan** (`benchmarks/corpus-v2/`); haqiqiy BMI matnlarida sifatning isboti emas. O'xshashlik foizi plagiatning avtomatik isboti emas. Morfologik qatlamlar **n=5 va n=15** so'rovga asoslangan — bu raqamlar **indikativ, statistik jihatdan aniq o'lchov emas**; bitta so'rov qo'shilsa/olib tashlansa foiz sezilarli siljishi mumkin. Bu hujjat [docs/decisions.md §5](../decisions.md)dagi uch-rejim modelini amalga oshirgandan keyingi o'lchov; oldingi (retrieval-only) bosqich uchun [uz-morph-v3.md](uz-morph-v3.md)ga qarang. **v3'dagi yangilik (2026-11-04):** `morphological`/`paraphrase`da precision=1.0 TA'RIFGA KO'RA ekanini aniqlashtirish (§0, §3), va shu kategoriya uchun HAQIQIY token-darajasidagi ground truth + qayta hisoblangan precision/recall/F1 (§4) — ortiqcha belgilangan tokenlar 0 ta, 15/15 so'rovda.

## 0. Qisqa xulosa

| Savol | Javob |
| --- | --- |
| Matching recall ko'tarildimi? | **Ha, sezilarli.** Morfologik so'rovlarning ENG QIYIN qatlamida (suffix% >= 35%, **n=5, indikativ**) matching recall 0.1802 -> **0.5238** (+0.3436). Past qatlamda (suffix% < 20%, n=10) 0.7234 -> **0.8545** (+0.1311). |
| Recall o'sishi precision hisobiga bo'ldimi? | **Yo'q — lekin ehtiyot bo'lib o'qing.** `morphological`/`paraphrase` kategoriyalarida ground truth `__FULL_TEXT__` (butun hujjat) bo'lgani uchun, bu ikkisida precision **TA'RIFGA KO'RA har doim 1.0** (har qanday topilgan moslik, albatta, "butun hujjat" ichida yotadi — bu o'lchangan natija emas, §3). Yolg'on musbat riskini haqiqatan cheklaydigan ikkita DALIL: (1) `hard_negative`+`unrelated`da (aniq snippet ground truth bilan) 0 ta yolg'on musbat, n=14, uch rejimning hech birida; (2) `verbatim`/`partial`/`quoted`da (aniq oraliqli ground truth bilan) uch rejim natijasi precision HAM, recall HAM aynan bir xil. |
| Offset/highlight kafolati buzildimi? | **Yo'q.** Har bir topilgan moslik hamon to'liq original so'zni (qo'shimchasi bilan) qamraydi — `backend/comparison/matching.py`dagi `span()` o'zgarmagan, faqat shingle tenglik tekshiruvi (`morph_key()`) yangi. Isbotlangan testlar: §5. |
| Foiz (coverage_percent) rejimlar orasida solishtiriladimi? | **YO'Q — qarang §6.** `retrieval+matching`da bir xil hujjat juftligi uchun foiz boshqa (odatda yuqoriroq) siyosat (`lexical-shingle-v2`) bilan hisoblanadi; bu "yaxshiroq natija" emas, BOSHQA METRIKA. |
| Eski so'rovlar (off/retrieval) o'zgardimi? | **Yo'q, bit-ma-bit bir xil.** `normalization="v2"`/`"v3"` default `matching_normalization="uz-latin-v2"` bilan chaqiriladi — `compare()`ning parametrsiz chaqiruvi bilan aynan bir xil natija. |
| Determinizm? | `--repeat 2` bilan tasdiqlangan: ikki pass CSV'si (timing ustunlaridan tashqari) bit-ma-bit bir xil. |
| UI qarori? | **Qabul qilindi, §7.** Frontend'dagi "tajriba" belgisi endi `v3-matching`ga bog'landi (retrieval-only o'zi amalda foydasiz edi: matching recall yuqori qatlamda 0.1802->0.1982, +0.018 — sezilmas). API/konfiguratsiyada uch rejim ham saqlanib qoldi. |

## 1. Uch rejim, yonma-yon (umumiy, 67 so'rov)

| Rejim | `normalization` | retrieval recall@1 | recall@5/@10 | MRR | matching precision | matching recall | matching F1 | FP so'rovlar (hard_negative+unrelated, n=14) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| off | `v2` | 0.6604 | 0.8302 | 0.7204 | 1.0000 | 0.6163 | 0.6424 | 0 |
| retrieval | `v3` | 0.7170 | 0.8491 | 0.7575 | 1.0000 | 0.6177 | 0.6448 | 0 |
| retrieval+matching | `v3-matching` | 0.7170 | 0.8491 | 0.7575 | 1.0000 | **0.6615** | **0.6848** | 0 |

Retrieval ustunlari `retrieval`/`retrieval+matching` orasida bir xil — kutilganidek, chunki ikkisi ham xuddi bir xil `fts_v3` nomzod tanlashdan foydalanadi (§ decisions.md §5 jadvali); farq faqat matching ustunlarida.

**Eslatma — "matching precision 1.0000" bu yerda aralash dalil:** 67 so'rovning 30 tasi (`morphological`+`paraphrase`) `__FULL_TEXT__` ground truth bilan, qolgani aniq snippet/`hard_negative`/`unrelated` bilan. `__FULL_TEXT__` so'rovlarda precision ta'rifga ko'ra 1.0 (yuqoridagi §0'ga qarang), shuning uchun bu qatordagi "1.0000" ning qaysi qismi haqiqiy o'lchov, qaysi qismi ta'rif ekanini bu jadvaldan ajratib bo'lmaydi — haqiqiy dalil uchun §3'ga (kategoriya kesimi) qarang.

## 2. Morfologik so'rovlar, suffix% qatlami bo'yicha (n=15, ikki qatlamga bo'lingan)

Qatlamlash manbasi: `benchmarks/corpus-v2/morph_strength.json`dagi `suffix_changed_ratio` (har bir morfologik so'rov uchun `scripts/measure_morph_strength.py` bilan oldindan hisoblangan). Yuqori qatlam (>= 35%) n=5, past qatlam (< 20%) n=10; oraliqda (20–35%) hech bir so'rov yo'q (toza ikkiga bo'linish).

| Qatlam | Rejim | matching precision (†) | matching recall | matching F1 | FP tokenlar |
| --- | --- | --- | --- | --- | --- |
| suffix% >= 35% (n=5) | off | 1.0000 | 0.1802 | 0.2719 | 0 |
| | retrieval | 1.0000 | 0.1982 | 0.3048 | 0 |
| | **retrieval+matching** | **1.0000** | **0.5238** | **0.6749** | **0** |
| suffix% < 20% (n=10) | off | 1.0000 | 0.7234 | 0.8379 | 0 |
| | retrieval | 1.0000 | 0.7234 | 0.8379 | 0 |
| | **retrieval+matching** | **1.0000** | **0.8545** | **0.9205** | **0** |

**(†) Bu jadvaldagi "matching precision" o'lchangan natija EMAS.** `morphological` kategoriyaning barcha so'rovlari `__FULL_TEXT__` ground truth bilan (§0, §3) — demak har bir qatorda 1.0000 ta'rifga ko'ra shunday chiqadi, stemming kolliziyasi yo'qligining DALILI emas (bunday kolliziya haqiqiy ground truth bo'lmasa, hech qanday predicted token uni aniqlay olmaydi). "FP tokenlar" ustuni ham shu sababdan har doim 0 — bu ustun faqat haqiqiy (snippet) ground truth bo'lgan kategoriyalarda (§3'dagi `hard_negative`/`unrelated`) ma'noli. **O'qilishi (eslatma: yuqori qatlam n=5, indikativ):** foyda aniq bir qatlamga tegishli, xuddi retrieval darajasidagi avvalgi o'lchov (uz-morph-v3.md §3) kabi — ENG QIYIN qatlamda (ko'p qo'shimcha o'zgargan so'rovlar) matching recall deyarli 3x ko'tariladi (0.18 -> 0.52), past qatlamda ham haqiqiy, lekin kichikroq foyda (0.72 -> 0.85). Bu recall o'sishi haqiqatan to'g'ri tokenlarni topganimi, yoki ortiqcha belgilashmi — HAQIQIY token-darajasidagi javob §4'da.

## 3. Ijobiy kategoriyalar bo'yicha precision/recall/F1 (recall o'sishi precision hisobigami?)

Har bir ijobiy kategoriya uchun (`expected_sources` bo'sh bo'lmagan so'rovlar), uch rejim yonma-yon:

| Kategoriya (n) | Ground truth turi | Rejim | precision | recall | F1 |
| --- | --- | --- | --- | --- | --- |
| `verbatim` (9) | 6 aniq snippet + 3 `__FULL_TEXT__` (to'liq nusxa so'rovlar) | off / retrieval / retrieval+matching | 1.0000 | 1.0000 | 1.0000 |
| `partial` (8) | aniq snippet (hammasi) | off / retrieval / retrieval+matching | 1.0000 | 0.7500 | 0.7500 |
| `paraphrase` (15) | **`__FULL_TEXT__` (hammasi)** | off / retrieval / retrieval+matching | 1.0000 | 0.0106 | 0.0200 |
| `quoted` (6) | aniq snippet (hammasi) | off / retrieval / retrieval+matching | 1.0000 | 0.6667 | 0.6667 |
| `morphological` (15) | **`__FULL_TEXT__` (hammasi)** | off | 1.0000 | 0.5423 | 0.6493 |
| | | retrieval | 1.0000 | 0.5483 | 0.6602 |
| | | **retrieval+matching** | **1.0000** | **0.7442** | **0.8386** |

**Muhim tuzatish:** yuqoridagi `paraphrase` va `morphological` qatorlaridagi precision=1.0000 **O'LCHANGAN NATIJA EMAS — TA'RIFGA KO'RA SHUNDAY**. Ikkala kategoriyaning ground truth'i `__FULL_TEXT__` (butun hujjat); `backend/benchmark/metrics.py`dagi `token_prf1()`da predicted_tokens har doim truth_tokens (= butun hujjat)ning qism to'plami bo'lgani uchun, bu ikki kategoriyada precision matematik jihatdan HAR DOIM 1.0 chiqadi — algoritm nima qilsa ham, hatto butunlay boshqa (noto'g'ri) tokenlarni belgilagan taqdirda ham emas (chunki "noto'g'ri" tushunchasining o'zi bu ground truth bilan aniqlanmagan). Shuning uchun bu ikki qator "stemming kolliziyasi yo'q" yoki "yolg'on musbat yo'q" degan xulosa uchun DALIL bo'la olmaydi.

**Yolg'on musbat riskini haqiqatan cheklaydigan dalillar** (aniq ground truth bilan o'lchangan): (1) `partial`(8) va `quoted`(6) — aniq snippet ground truth, uch rejim ORASIDA precision HAM, recall HAM AYNAN BIR XIL, demak v3-matching bu ikki kategoriyaga hech qanday (ijobiy ham, salbiy ham) ta'sir qilmagan; (2) `verbatim`(9)ning 6 ta aniq-snippet so'rovi ham xuddi shunday o'zgarmagan; (3) `hard_negative`+`unrelated` (n=14, aniq snippet/bo'sh ground truth, §0) — uch rejimning hech birida yolg'on musbat yo'q. `morphological`/`paraphrase`dagi precision=1.0 bu ro'yxatga QO'SHILMAYDI (sabab yuqorida).

**Xulosa (qayta ifodalangan):** `morphological` kategoriyada recall sezilarli o'sadi (+0.2019, 0.5423->0.7442), va bu nazorat to'plamida BU KATEGORIYANING O'ZIDA precision pasaymadi (chunki pasaya olmaydi — ta'rifga ko'ra). Recall o'sishi haqiqiy yolg'on musbatlar hisobiga bo'lganmi yoki yo'qmi — HAQIQIY token-darajasidagi javob §4'da: YO'Q.

## 4. Morfologik toifa uchun HAQIQIY token-darajasidagi precision/recall/F1

**Muammo (§2/§3'dan):** `morphological`ning ground truth'i `__FULL_TEXT__` (butun hujjat) bo'lgani uchun, uning precision=1.0000 raqami ta'rifga ko'ra shunday chiqadi — bu v3-matching haqiqatan to'g'ri tokenlarni topayotganining yoki ortiqcha (noto'g'ri) belgilayotganining DALILI emas edi.

**Tuzatish:** `scripts/measure_morph_strength.py`ga yangi funksiya qo'shildi — `token_level_ground_truth()`. Bu ham xuddi `measure()` kabi `difflib.SequenceMatcher`dan foydalanadi (so'rov va manba tokenlari orasidagi alignment — har bir morfologik so'rov sof almashtirish, `pure_substitution=True`, bo'lgani uchun bu alignment to'liq, chetga chiqarilgan/qo'shilgan so'zsiz), lekin HAR BIR so'rov tokenini (nafaqat kontent so'zlarni) uchta toifaga ajratadi:

- **"equal"** — manbadagi tokeniga harf-ma-harf teng (o'zgarmagan) — haqiqiy moslik kutiladi.
- **"replace" + `shares_stem()`=True** — boshqa so'zga almashtirilgan, lekin manba so'zi bilan bir xil o'zakni ulashadi (sof qo'shimcha o'zgarishi) — to'g'ri stemmer buni topishi KERAK.
- **"replace" + `shares_stem()`=False** — haqiqiy sinonim/butunlay boshqa so'z (qo'shimcha o'zgarishi emas) — hech qanday lug'atsiz/stemming usuli buni qonuniy ravishda topa olmaydi, shuning uchun bu ground truth'dan CHIQARIB TASHLANADI.

Natija (`expected_match_token_indices` = "equal" + "replace+stem" indekslari) `benchmarks/corpus-v2/morph_strength.json`ning har bir so'rov yozuviga `token_ground_truth` maydoni sifatida qo'shildi (`manifest.json`dagi `__FULL_TEXT__` O'CHIRILMADI — ikkisi yonma-yon turadi, chunki `__FULL_TEXT__` retrieval-darajasidagi metrikalar uchun hamon to'g'ri konventsiya). 15 so'rovning barchasida chiqarib tashlangan tokenlar soni kichik: 0–12 ta (query_token_count 78–310 orasida) — bu kutilgan, chunki morfologik so'rovlar deyarli sof almashtirish.

Yangi `scripts/measure_morph_token_precision.py` skripti shu haqiqiy ground truth bilan (retrieval'ni §6'dagi kabi chetlab, har bir so'rov o'zining haqiqiy `expected_sources[0]`'iga qarshi) precision/recall/F1'ni qayta hisoblaydi:

| Rejim | precision (haqiqiy) | recall (haqiqiy) | F1 (haqiqiy) | ortiqcha belgilangan tokenlar |
| --- | --- | --- | --- | --- |
| off/retrieval (`matching_normalization=uz-latin-v2`) | **1.0000** (n=14/15†) | 0.5576 | 0.6670 | **0** (0/15 so'rovda) |
| **retrieval+matching** (`matching_normalization=uz-latin-v3`) | **1.0000** (n=15/15) | **0.7561** | **0.8460** | **0** (0/15 so'rovda) |

(†) `uz_morph_adabiyot`da off/retrieval bilan BIRON TOKEN topilmagan (predicted_tokens bo'sh) — bu holatda precision aniqlanmagan (`token_prf1()` qoidasi), shuning uchun o'rtacha 14/15 so'rov ustida olingan; shu so'rovda recall=0.0, v3-matching bilan esa 0.3049ga ko'tariladi.

**JAVOB (asosiy savol):** v3-matching belgilagan tokenlar HAQIQATAN mos tokenlar — ortiqcha belgilanganlari **YO'Q**. Barcha 15 so'rovning hech birida, hech qanday rejimda bitta ham ortiqcha (haqiqiy ground truth'dan tashqari) token predicted_tokens ichiga tushmagan — `morph_strength.json`dagi barcha "replace+synonym" (haqiqiy sinonim) tokenlar ikkala rejimda ham chetda qoldi, stemming ularni hech qachon manba so'ziga "yopishtirmadi". Haqiqiy precision — endi o'lchangan natija, ta'rif emas — hamon 1.0, va recall o'sishi (0.5576->0.7561) to'liq haqiqiy tokenlarni topish hisobiga, yolg'on musbatlar hisobiga EMAS.

Reproduksiya: `.\.venv\Scripts\python.exe scripts\measure_morph_strength.py` (ground truth'ni `morph_strength.json`ga yozadi), keyin `.\.venv\Scripts\python.exe scripts\measure_morph_token_precision.py` (natijani `benchmarks/corpus-v2/results/morph_token_precision.json`ga yozadi). Yangi alignment mantig'i (`token_level_ground_truth()`) uchun 7 ta yangi unit test: `backend/tests/test_measure_morph_strength.py::TokenLevelGroundTruthTests` (§8).

## 5. Offset/highlight kafolati — testlar, da'vo emas

Qabul mezoni "Mos parcha normallashtirilgan fazoda topiladi, lekin foydalanuvchiga ORIGINAL matndagi TO'LIQ so'z belgilanishi shart" quyidagi testlar bilan isbotlangan (ikkisi ham `--repeat`siz, bitta aniq lokal yurgizishda o'tadi, Postgres fixture'siz birinchisi, fixture bilan ikkinchisi):

- `backend/tests/test_comparison.py::MatchingTests::test_v3_matching_finds_morphological_variants_v2_misses` — olti so'zli sun'iy jumla, har bir so'z faqat qo'shimchasi bilan farq qiladi (`kitoblarni`/`kitoblardan` va h.k.). v2 bilan `matched_tokens=0`; `matching_normalization="uz-latin-v3"` bilan `matched_tokens=6`, va highlight matni (`match["document"]["text"]`) hujjatning TO'LIQ matniga teng — qisqartirilgan o'zakka emas.
- `backend/tests/test_comparison.py::MatchingTests::test_v3_matching_does_not_merge_unrelated_words_into_one_stem` — bog'liq bo'lmagan so'zlar (`test_uz_latin_v3.py`dagi kolliziya-xavfsizlik so'zlaridan) v3-matching bilan ham mos deb belgilanmaydi.
- `backend/tests/test_corpus_integration.py::CorpusComparisonTests::test_v3_matching_finds_what_v3_retrieval_only_misses` — to'liq API (`POST /compare?include_corpus=true&normalization=v3-matching`) orqali, haqiqiy (disposable) PostgreSQL ustida: `normalization="v3"` bilan korpus nomzodi topiladi, lekin `matches=[]` (v2 matching suffix farqini ko'rmaydi); `normalization="v3-matching"` bilan xuddi shu nomzod endi `matches` bilan qaytadi, va highlight matni CHECKED tomonning TO'LIQ original so'zlarini (o'z qo'shimchasi bilan) qamraydi.

Mavjud v2 offset testlari (`test_unicode_apostrophes_whitespace_and_original_coordinates`, `test_invisible_highlight_with_prefix_and_suffix`, `test_v3_retrieval_never_changes_what_the_comparison_highlights` va h.k.) o'zgarishsiz o'tadi (§8).

## 6. Foiz inflyatsiyasi — rejimlar orasida foiz TAQQOSLANMAYDI

**Uslub:** retrieval'ni chetlab, HAR BIR ijobiy so'rov o'zining AYNAN BIR XIL kutilgan manbasiga (`manifest.json`dagi `expected_sources[0]`) qarshi ikki marta solishtirildi — bir marta `matching_normalization="uz-latin-v2"` (= `off` VA `retrieval` rejimlari, ikkisi aynan bir xil matching beradi, chunki matching retrieval rejimidan mustaqil), bir marta `"uz-latin-v3"` (= `retrieval+matching`). Bu sof matching-darajasidagi ta'sirni retrieval qaysi nomzodlarni tanlashidan butunlay ajratadi (n=53 ijobiy so'rov, hal qiluvchi manbasi nazorat to'plamida topilgan).

| Kategoriya | n | o'rtacha farq (pp) | eng katta farq (pp) | nechta so'rovda farq > 0 |
| --- | --- | --- | --- | --- |
| `verbatim`/`partial`/`paraphrase`/`quoted` (jami) | 38 | **0.00** | 0.00 | 0 / 38 |
| `morphological` | 15 | **+19.59** | **+41.03** | 15 / 15 |

**Xulosa:** foiz o'zgarishi FAQAT `morphological` kategoriyada bor, va u yerda HAR DOIM musbat (foiz hech qachon kamaymaydi) — bu kutilgan, chunki v3-matching faqat qo'shimcha farq qiluvchi so'zlarni QO'SHIMCHA ravishda mos deb belgilaydi, hech qachon oldin topilgan moslikni olib tashlamaydi. Boshqa to'rt kategoriyada foiz bir TIYINGA ham o'zgarmaydi.

**Aniq misol** (`uz_morph_pedagogika`, eng katta farq): kutilgan manbaga nisbatan `off`/`retrieval` bilan qoplash **8.97%** (7/78 token, bitta qisqa moslik: *"An'anaviy ma'ruza shaklidagi darslardan farqli o'laroq, faol"*). `retrieval+matching` bilan **50.00%** (39/78 token) — qo'shimcha to'rt parcha mos deb belgilanadi, masalan *"faol ta'lim usullarining o'quvchilarda mustaqil fikrlash"* va *"Guruhli muhokamalarda, loyihaviy ishlarda va muammoli vaziyatlarni tahlil qilishlar bunday yondashuvlarning asosiy"* — bular hujjat va manbada FAQAT qo'shimchalari bilan farq qiladigan so'zlar zanjiri (masalan "fikrlashga"/"fikrlash").

**Talqin — "inflyatsiya" emas, tiklanish (endi §4 bilan TASDIQLANGAN):** `morphological` so'rovlar deyarli sof so'z-ma-so'z almashtirish (`morph_strength.json`dagi `pure_substitution=True`, §2) bo'lgani uchun, haqiqiy (semantik) qoplash manbaga nisbatan ~100%ga yaqin bo'lishi kutilgan edi. §4'dagi haqiqiy token-darajasidagi ground truth buni aynan shu misol uchun tasdiqlaydi: `uz_morph_pedagogika`ning barcha 78 tokeni `token_ground_truth.non_matchable_token_indices` bo'yicha BO'SH — ya'ni bu aniq so'rovda haqiqiy ground truth AYNAN butun hujjatning o'zi (sinonim bilan almashtirilgan, demak "topib bo'lmaydigan" birorta ham token yo'q). Demak 8.97% -> 50.00% ko'tarilishi bu aniq misolda 100% TASDIQLANGAN TIKLANISH, "inflyatsiya" (ya'ni yolg'on/haqiqatga mos kelmaydigan o'sish) emas — va 15 so'rovning barchasi bo'yicha umumlashtirilgan natija ham buni qo'llab-quvvatlaydi: ortiqcha belgilangan tokenlar soni 0/15 so'rovda (§4).

**QOIDA (docs/decisions.md §5'ga ham yozilgan):** `retrieval+matching` (`v3-matching`) bilan hisoblangan `coverage_percent` `off`/`retrieval` (`v2`/`v3`) bilan hisoblangan foiz BILAN SOLISHTIRILMAYDI — bu ikkisi boshqa siyosat (`parameters.algorithm_version`: `lexical-shingle-v1` vs `lexical-shingle-v2`) bilan hisoblangan, boshqa METRIKA. Bir xil hujjat ikki marta (bir marta har bir rejimda) tekshirilib, foizlar "oldin/keyin" sifatida taqqoslanmasligi kerak — har bir rejimning o'z foizi faqat O'ZI ICHIDA (masalan vaqt o'tishi bilan, bir xil rejimda qayta tekshirish) ma'noli.

## 7. UI qarori — "tajriba" belgisi `retrieval+matching`ga bog'landi

§1–§3dagi o'lchov shuni ko'rsatdi: **retrieval-only ("v3") o'zi amalda foydasiz** — eng qiyin qatlamda ham matching recall atigi +0.018 ko'tariladi (0.1802->0.1982), foydalanuvchi buni deyarli sezmaydi, chunki oxir-oqibat KO'RINADIGAN narsa — highlight qilingan moslik — hamon v2'da qoladi. Shu sababli:

- `frontend/app/comparison.tsx`dagi mavjud "O'zbekcha qo'shimchalarni hisobga olish (tajriba)" belgisi endi `normalization=v3-matching` yuboradi (avval `v3` edi). Belgi matni ham yangilandi: endi aniq aytilgan — bu ham nomzod tanlashga, ham mos parchani belgilashga ta'sir qiladi, va ko'rsatilgan foiz alohida siyosat (`lexical-shingle-v2`) bilan hisoblanadi, standart natijalar bilan solishtirilmaydi (§6dagi qoida).
- **API/konfiguratsiyada uch rejim ham saqlanib qoldi** — `normalization=v2`/`v3`/`v3-matching` barchasi hamon ishlaydi (`backend/comparison/api.py`), shunda oldingi o'lchovlar (uz-morph-v3.md, retrieval-only) istalgan vaqt qayta ishlab chiqarilishi mumkin. Faqat frontend'ning BITTA checkbox'i o'zining maqsadini (sof retrieval ablatsiyasidan foydalanuvchiga haqiqiy foyda beruvchi rejimga) o'zgartirdi.
- **Brauzerda tasdiqlangan (haqiqiy topilma):** birinchi urinishda checkbox yoniq bo'lsa ham hisobot hamon `uz-latin-v2`/`lexical-shingle-v1` qaytarardi — sabab `frontend/lib/proxy.ts`dagi query-param oq ro'yxati hali faqat eski `normalization=v3` qiymatini tanir edi (`=== "v3"` tekshiruvi), `v3-matching`ni esa jim tashlab yuborardi, shuning uchun backend hech qanday `normalization` parametrisiz, standart `v2`da ishlar edi. Bu — `comparison.tsx`dagi checkbox simlanishining o'zi TO'LIQ emasligini anglatardi. `proxy.ts`ning oq ro'yxatiga `v3-matching`ni ham qo'shib tuzatildi (algoritm/matching mantig'iga tegilmadi — bu faqat frontend proxysining query-param forward qilish qatlami). Tuzatishdan keyin: belgi o'chiq bo'lganda hisobot "Siyosat: uz-latin-v2. Algoritm: lexical-shingle-v1." (39 tokendan 6 tasi mos, 15.38%) ko'rsatadi; yoniq bo'lganda va natijada morfologik farqli manba topilganda "Siyosat: uz-latin-v3. Algoritm: lexical-shingle-v2." (39 tokendan 20 tasi mos, 51.28%) va highlight TO'LIQ so'zni (qo'shimchasi bilan) qamraydi — ikkalasi ham bitta qo'lda tayyorlangan sinov juftligida (`kitoblardan`/`kitoblarni` va h.k., 5 ta so'z juftligi) brauzerda bevosita tasdiqlandi.

## 8. Darvoza

190 backend testi (183 + 7 yangi: `TokenLevelGroundTruthTests` sinfi, `backend/tests/test_measure_morph_strength.py`'da — §4'dagi `token_level_ground_truth()` alignment mantig'i uchun), barchasi o'tadi. 183 ning o'zi 178 + 5 (`test_matching_normalization_defaults_to_v2_unchanged`, `test_matching_normalization_rejects_unknown_value`, `test_v3_matching_finds_morphological_variants_v2_misses`, `test_v3_matching_does_not_merge_unrelated_words_into_one_stem`, `test_v3_matching_finds_what_v3_retrieval_only_misses`). Hech biri backend matching kod mantig'iga tegilmagani uchun o'zgarmadi (`proxy.ts` tuzatishidan keyin ham, bu bosqichdagi docs/scripts o'zgarishlaridan keyin ham). `off` rejimida (parametrsiz `compare()` chaqiruvi) natijalar bit-ma-bit o'zgarmagan — buni `test_matching_normalization_defaults_to_v2_unchanged` va qolgan 178 testning o'zgarishsiz o'tishi tasdiqlaydi. Determinizm `scripts/eval_retrieval.py --corpus corpus-v2 --repeat 2` bilan tasdiqlandi. Frontend: `npm run lint`/`typecheck`/`build` uchtasi ham `comparison.tsx` + `proxy.ts` o'zgarishidan keyin muvaffaqiyatli. (Lokal dasturlash muhitiga oid, algoritmga aloqasi yo'q bitta qo'shimcha tuzatish: `next.config.ts`ga `allowedDevOrigins: ["127.0.0.1"]` qo'shildi — Next.js 16 dev server standart bo'yicha 127.0.0.1'dan kelgan dev-resurslarini cross-origin deb bloklaydi, bu esa faqat `next dev`ga tegishli, production build/`next start`ga ta'sir qilmaydi.)

## 9. Tekshirilmagan qolgan narsalar

- **Haqiqiy BMI matnlarida tasdiqlanmagan.** Barcha raqamlar 59/67 hajmli sintetik nazorat to'plamidan (`benchmarks/corpus-v2/`); real foydalanuvchi hujjatlarida yolg'on musbat xavfi bu yerda kuzatilgan 0dan farqli bo'lishi mumkin.
- **`MIN_WORD_LEN_TO_STRIP`/`MIN_STEM_LEN` qayta sozlanmadi.** `backend/comparison/uz_latin_v3.py`dagi xavfsizlik chegaralari (7/4 belgi) o'zgarishsiz qoldi; bu o'lchov ularning matching darajasidagi tarqalishini (shunday chegaralar bilan) tasdiqladi, lekin ularni qattiqlashtirish/yumshatishni tekshirmadi.
- **`paraphrase`/`partial`/`quoted`/`verbatim` kategoriyalari suffix% bilan qatlamlanmagan** — ular `suffix_changed_ratio` bilan hisoblanmaydi (faqat `morphological` toifasi uchun hisoblangan, `scripts/measure_morph_strength.py`ning o'z qamrovi bo'yicha); umumiy (barcha toifalar) raqam §1da, kategoriya-kesimli raqam §3da bor.
- **§6dagi foiz-inflyatsiya tahlili commit qilinmagan skript bilan hisoblangan** (bir martalik tahlil, `matching.compare()`ning o'zidan, retrieval'ni chetlab) — natijalar shu hujjatda qayd etilgan, lekin skriptning o'zi repo'da saqlanmagan (qayta hisoblash kerak bo'lsa, usul §6'da yozilgan: har bir ijobiy so'rov + uning `expected_sources[0]`'i uchun `compare(..., matching_normalization=...)`ni ikki marta chaqirish).
- **`shares_stem()` evristikasi qo'pol.** §4'dagi token-darajasidagi ground truth `shares_stem()`ga (kamida 3 harfli umumiy prefiks) tayanadi — bu haqiqiy morfologik tahlilchi emas, shunchaki belgi asosidagi evristika (`scripts/measure_morph_strength.py`ning o'zidagi eslatma). Bir nechta "replace_synonym" deb belgilangan juftlik (masalan `etadi`->`etmoqda`, `bo'ldi`->`aylandi`) difflib'ning POZITSION pairing'i tufayli gap qayta tuzilganda tasodifan noto'g'ri juftlanган bo'lishi mumkin — bu qo'pollik natijada haqiqiy ground truth'ni BIROZ toraytiradi (ba'zi haqiqiy qoplashlarni "sinonim" deb noto'g'ri chetlashi mumkin), lekin KENGAYTIRMAYDI (hech qachon haqiqatan sinonim bo'lgan so'zni "mos" deb hisoblamaydi) — shuning uchun §4'dagi 0 ta ortiqcha-belgilash xulosasi bu qo'pollik tomonidan ZAIFLASHTIRILMAYDI, faqat recall raqami (0.5576/0.7561) biroz past baholangan bo'lishi mumkin (haqiqiy qoplash ehtimol ozgina yuqoriroq).
- **§4'dagi tahlil ham retrieval'ni chetlab o'tadi** (§6 bilan bir xil uslub, usiz izohlangan) — "off" va "retrieval" rejimlari u yerda bitta qatorga qo'shilgan (`matching_normalization=uz-latin-v2` ikkisida ham bir xil), chunki matching retrieval normalizatsiyasidan mustaqil (docs/decisions.md §5). Haqiqiy retrieval orqali (nomzod tanlashning o'zi xato bo'lgan holatlarni ham hisobga olib) qayta tekshirish hali qilinmagan.
