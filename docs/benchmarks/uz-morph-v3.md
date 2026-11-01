# uz-latin-v3 o'lchovi va tavsiya — C bosqichi

Versiya 1 · 2026-10-18 · Kod: [backend/comparison/uz_latin_v3.py](../../backend/comparison/uz_latin_v3.py) · Harness: [scripts/eval_retrieval.py](../../scripts/eval_retrieval.py) (`ablation_uz_latin_v3`) · Nazorat to'plami: [benchmarks/corpus-v2/](../../benchmarks/corpus-v2/) · Xom ma'lumot: [uz-morph-v3-token-diagnostics.csv](uz-morph-v3-token-diagnostics.csv), [uz-morph-v3-retrieval-delta.csv](uz-morph-v3-retrieval-delta.csv)

**MAJBURIY OGOHLANTIRISH.** Raqamlar **sintetik, 59 hujjatli/67 so'rovli nazorat to'plamidan**; haqiqiy BMI matnlarida sifatning isboti emas. O'xshashlik foizi plagiatning avtomatik isboti emas. FTS reytingi (`ts_rank`) foiz yoki o'xshashlik ko'rsatkichi emas — faqat nomzod saralash vositasi. Bu hujjat **faqat o'lchov va tavsiya**; `backend/comparison/uz_latin_v3.py`, migratsiyalar yoki `corpus.py` ushbu bosqichda o'zgartirilmagan.

## 0. Qisqa xulosa

| Savol | Javob |
| --- | --- |
| v3 retrieval darajasida haqiqiy foyda beradimi? | **Ha, o'lchanadigan va kategoriyaga mos.** Morfologik so'rovlarning eng qiyin (yuqori suffix%) qatlamida recall@5/@10 +20pp, MRR +0.10. Past suffix% qatlamida farq yo'q (ikkalasi ham shiftda). |
| Matching darajasida foyda bormi? | Deyarli yo'q, **dizayn bo'yicha** — matching hamon faqat v2 tokenlarida ishlaydi (§4). |
| Xavfsiz ishlatish mumkinmi? | **Hozircha yo'q — tasdiqlangan nuqson bor** (§2): index va query yo'llari bir xil so'zni turlicha himoyalaydi, chunki `tokenize()` katakchani query tomonida stem qilishdan OLDIN kichik harfga aylantiradi. Bu v3'ning o'zi himoya qilishi kerak bo'lgan aynan shu toifadagi so'zlarni (atoqli ot + qo'shimcha) index/so'rov orasida mos kelmay qoladi. |
| Eng ko'p nima bloklaydi? | "Qisqa so'z" himoyasi (≤7 belgi) — barcha tokenlarning 50.5%i shu sababli tegilmaydi, boshqa har qanday sababdan ko'proq (§1). |

## 1. C1 — token darajasidagi diagnostika

Har bir token (`uz_latin_v3._WORD` chegarasi bilan) besh toifaga ajratildi: **stemmed** (haqiqatan qirqilgan), **too_short** (≤7 belgi, hech qachon ko'rilmagan), **stem_too_short** (mos qoida topildi, ammo qolgan o'zak <4 belgi bo'lib rad etildi), **no_matching_suffix** (yetarlicha uzun, lekin oxiri hech bir qoidaga to'g'ri kelmaydi), **foreign_guard** (bosh harf yoki raqam tufayli butunlay o'tkazib yuborildi).

### 1.1 Korpus hujjatlari, til bo'yicha

| Til | Jami token | stemmed | too_short | stem_too_short | no_matching_suffix | foreign_guard |
| --- | --- | --- | --- | --- | --- | --- |
| `uz_latin` | 6512 | 1760 (**27.0%**) | 3154 (48.4%) | 19 (0.3%) | 782 (12.0%) | 797 (12.2%) |
| `en` | 3454 | 12 (0.3%) | 2098 (60.8%) | 0 | 918 (26.6%) | 426 (12.3%) |
| `ru` | 3280 | 0 (0.0%) | 1500 (45.7%) | 0 | 1331 (40.6%) | 449 (13.7%) |

### 1.2 So'rovlar, kategoriya bo'yicha (stemmed ulushi)

| Kategoriya | Jami token | stemmed | ulush |
| --- | --- | --- | --- |
| `morphological` | 3556 | 1133 | **31.9%** |
| `paraphrase` | 1480 | 181 | 12.2% |
| `verbatim` | 932 | 98 | 10.5% |
| `hard_negative` | 672 | 67 | 10.0% |
| `quoted` | 324 | 37 | 11.4% |
| `partial` | 495 | 51 | 10.3% |
| `unrelated` | 445 | 35 | 7.9% |

### 1.3 Umumiy (korpus + barcha so'rov tokenlari, 21150 ta)

`too_short` (50.5%) yagona eng katta blokловчи omil — undan keyin `no_matching_suffix` (21.2%), `foreign_guard` (11.9%), `stemmed` (16.0%), `stem_too_short` esa arzimas (0.3%). **Xulosa: qoida to'plamining o'zi yetarlicha ishlayotgan joylarda (≥7 belgili, mos qoidali so'zlarda) deyarli hech narsa rad etilmaydi (`stem_too_short` 0.3%) — asosiy cheklov qamrov (qancha so'z umuman "yetarlicha uzun va mos qoidali"), aniqlik emas.** Agar qamrovni oshirish kerak bo'lsa, `MIN_WORD_LEN_TO_STRIP`ni (hozir 7) pasaytirish eng ko'p foyda beradi — lekin bu xavfsizlik chegarasini ataylab yumshatish bo'ladi, raqam bilan asoslanmagan.

### 1.4 Topilgan nuqson: ingliz so'zlarining noto'g'ri "stem" qilinishi

`en` tokenlarining 15 tasi (0.3%, lekin **tizimli**, tasodifiy emas) noto'g'ri qirqildi — chunki ular tasodifan o'zbekcha qoidalar bilan bir xil harf ketma-ketligida tugaydi:

| So'z | Qirqilgan natija | Qaysi qoida |
| --- | --- | --- |
| `learning` (6 marta, pedagogy/history) | `lear` | `-ning` (egalik kelishigi) |
| `molecular` (3 marta, biology/physics) | `molecu` | `-lar` (ko'plik) |
| `planning` | `plan` | `-ning` |
| `screening` | `scree` | `-ning` |
| `threatening` | `threate` | `-ning` |

Bu "rus/ingliz so'zini kesmaslik" himoyasining **o'lchangan, haqiqiy bo'shlig'i**: joriy himoya faqat bosh harf/raqamga qaraydi, lug'at yo'qligi sababli "-ning" bilan tugaydigan "-ing" fe'l shakllarini (ingliz tilida juda keng tarqalgan) va "-lar" bilan tugaydigan lotincha-asosli sifatlarni ("molecular", "particular", "similar", "popular", "regular" va sh.k.) ajrata olmaydi.

## 2. C2 — simmetriya tekshiruvi: NUQSON TOPILDI

**Da'vo emas, kod va bajarilish bilan isbotlangan.** `stem_text(` ikki joyda chaqiriladi — [backend/corpus.py:98](../../backend/corpus.py#L98) (so'rov tomoni, `query_windows`) va [backend/corpus.py:157](../../backend/corpus.py#L157) (indeks tomoni, `add_document`). Ikkisi ham bir xil funksiyani chaqiradi — lekin unga YUBORILGAN MATNNING O'ZI bir xil emas:

- **Indeks tomoni** `stem_text(chunk_text)` — `chunk_text` original, katta-kichik harfi saqlangan matn.
- **So'rov tomoni** `query_windows()` `tokenize(text)`ning token QIYMATLARIDAN (`matching.py:40`, `.casefold()` allaqachon bajarilgan) iborat iborani quradi, SHUNDAN KEYIN uni `stem_text()`ga yuboradi.

Natijada `uz_latin_v3._looks_non_uzbek()`ning bosh-harf-asosidagi himoyasi **so'rov tomonida hech qachon ishlamaydi** — u faqat indeks tomonida ishlaydi. Bajarilish bilan tasdiqlangan misol:

```
Kirish (xom, katta harfli):  'Alisher Navoiyning ijodi ... kotarildi.'
INDEKS tomoni natijasi:      'Alisher Navoiyning ijodi ... kotaril.'   <- "Navoiyning" HIMOYALANDI
SO'ROV tomoni kirishi:       'alisher navoiyning ijodi ... kotarildi' <- tokenize() allaqachon kichiklashtirgan
SO'ROV tomoni natijasi:      'alisher navoiy ijodi ... kotaril'       <- "navoiy" QIRQILDI
```

Butun o'zbekcha nazorat to'plami bo'yicha o'lchab ko'rilganda: **11695 solishtirilgan o'zbekcha tokendan 222 tasi (1.90%)** xuddi shu sinfga tushadi — indeks tomonida himoyalangan (chunki asl matnda bosh harfli), lekin so'rov tomonida stem qilingan (chunki `tokenize()` bosh harfni allaqachon yo'qotgan). Misollar: `Navoiyning`→indeksda saqlanadi/so'rovda `navoiy`ga qirqiladi; `Xayyomning`→`xayyom`; `Samarqanddagi`→`samarqand`; `Ularning`→`ular`.

**Oqibat:** agar korpus hujjatida "Navoiyning" so'zi bo'lsa va so'rovda aynan shu so'z ishlatilsa, indeksdagi leksema (`navoiyning`, qirqilmagan — Postgres faqat kichiklashtiradi, qo'shimchani olib tashlamaydi) va so'rovdagi leksema (`navoiy`, qirqilgan) **mos kelmaydi**. Bu v3'ning aynan shu holat uchun mo'ljallangan himoyasini (atoqli ot/qisqartma qoldirish) index/query orasida ishlamay qoldiradi — ya'ni himoya o'zi ishlaydi, lekin ikki tomon orasida IZCHIL emas.

**Bu C2 vazifasi talab qilgan "to'xta"**: simmetriyani "isbotlash" o'rniga nuqsonni o'lchab, hujjatlashtirib, C5'ga tavsiya sifatida olib o'tdim (pastda).

## 3. C3 — retrieval darajasidagi delta (asosiy raqam)

`backend.benchmark.metrics.aggregate_retrieval()`, `raw-pass1.csv`dan (determinizm `--repeat 2` bilan tasdiqlangan — pass1/pass2 `retrieval_seconds`/`matching_seconds`dan boshqa barcha ustun bo'yicha bir xil). To'liq jadval: [uz-morph-v3-retrieval-delta.csv](uz-morph-v3-retrieval-delta.csv).

| Qatlam (n so'rov) | Konfiguratsiya | recall@1 | recall@5 | recall@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| **morfologik, YUQORI suffix% (≥35%)** — adabiyot, adabiyot_2, biologiya_2, pedagogika, tarix (n=5) | v2 (baseline) | 0.4000 | 0.8000 | 0.8000 | 0.5067 |
| | **v3** | 0.4000 | **1.0000** | **1.0000** | **0.6067** |
| **morfologik, PAST suffix% (<20%)** — biologiya_3, ekologiya_2/3, falsafa, iqtisodiyot_2, kimyo, pedagogika_2/3, tarix_2/3 (n=10) | v2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| | v3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| morfologik, hammasi (n=15) | v2 | 0.8000 | 0.9333 | 0.9333 | 0.8356 |
| | v3 | 0.8000 | 1.0000 | 1.0000 | 0.8689 |
| paraphrase (n=15) | v2 | 0.4667 | 0.7333 | 0.7333 | 0.5800 |
| | v3 | 0.5333 | 0.7333 | 0.7333 | 0.6133 |
| partial (n=8) | v2 = v3 | 0.6250 | 0.7500 | 0.7500 | 0.6875 |
| quoted (n=6) | v2 = v3 | 0.5000 | 0.6667 | 0.6667 | 0.5417 |
| verbatim (n=9) | v2 = v3 | 0.8889 | 1.0000 | 1.0000 | 0.9111 |
| **BARCHASI (n=53, N/A bo'lganlar chetlangan)** | v2 | 0.6604 | 0.8302 | 0.8302 | 0.7204 |
| | **v3** | **0.6792** | **0.8491** | **0.8491** | **0.7393** |

**O'qilishi:** v3'ning foydasi aniq bir qatlamga tegishli — morfologik so'rovlarning ENG QIYIN (yuqori suffix o'zgarishi) qismida, qayerda v2 recall@5/@10'da 0.80'da to'xtagan (5 so'rovdan 1 tasi hech qachon top-5'ga kirmagan), v3 buni 1.00'ga ko'taradi. Past qatlamda ikkalasi ham allaqachon shiftda (1.0000) — demak bu yerda farq BO'LISHI HAM MUMKIN EMAS, v3'ning "zaifligi" emas. `paraphrase`'da ham kichik, lekin haqiqiy foyda bor (ba'zi paraphrase so'rovlar tasodifan o'zbekcha qo'shimcha farqlariga ega).

## 4. C4 — matching darajasidagi delta

| Konfiguratsiya | Morfologik matching recall | F1 | FP | Umumiy matching recall | F1 | FP |
| --- | --- | --- | --- | --- | --- | --- |
| v2 (baseline) | 0.5423 | 0.6493 | 0 | 0.6163 | 0.6424 | 0 |
| v3 (ablation) | 0.5483 | 0.6602 | 0 | 0.6177 | 0.6448 | 0 |

**Bu raqamlar dizayn bo'yicha deyarli bir xil, va shunday bo'lishi SHART.** `matching.compare()` — ya'ni qaysi belgi oralig'i "mos" deb belgilanishi — hech qachon `chunk_text_uz_latin_v3`, `fts_v3` yoki `normalization` parametrini ko'rmaydi; u faqat `matching.tokenize()`ning o'zgarmagan v2 tokenlarida ishlaydi (`backend/comparison/matching.py`, `compare()` funksiyasi — `normalization` argumenti umuman yo'q). Yuqoridagi arzimas farq (0.5423→0.5483) **bevosita FTS natijasida emas**, balki **qaysi hujjatlar nomzod sifatida tanlanishi** o'zgarishidan kelib chiqadi (§3dagi retrieval farqi) — ko'proq to'g'ri hujjat nomzodga kirgach, compare() ularning ustida ishlaydi va ozgina ko'proq matn qamraydi. Demak bu yerdagi raqam v3'ning "kuchi"ni EMAS, v3'ning retrieval ta'sirini BILVOSITA aks ettiradi.

## 5. C5 — xulosa va tavsiya

**(a) v3 retrieval darajasida haqiqiy foyda beradimi?** Ha — §3'dagi YUQORI qatlamda aniq, o'lchangan, qatlamga mos foyda (recall@5/@10 +20pp, MRR +0.10). PAST qatlamda farq yo'q, chunki u allaqachon shiftda — bu kutilgan va mantiqiy, nazorat to'plamining o'zi notekis bo'lgani uchun (B1'da qayd etilgan).

**(b) Keyingi mantiqiy qadam — TAKLIF, IMPLEMENTATSIYA QILINMAGAN:**

Matching bosqichini ham v3 normallashtirilgan tokenlarda ishlatish — ya'ni `compare()`ga alternativ tokenizatsiya yo'lini qo'shish — nazariy jihatdan matching recall'ni ham ko'tarishi mumkin (hozir morfologik matching 0.54'da, chunki exact/shingle algoritmi aynan bir xil so'z shaklini talab qiladi). Lekin bu MEN TAVSIYA QILMAYDIGAN qadam, hech bo'lmasa quyidagilar hal qilinmaguncha:

1. **Avval §2'dagi nuqson tuzatilishi SHART.** Agar matching ham v3'dan foydalansa, index/query assimetriyasi endi faqat "candidate topilmadi"ga emas, balki **noto'g'ri highlight/offset**ga olib kelishi mumkin — bu `docs/requirements.md`dagi "original matn va offset o'zgarmasligi" talabini buzadi. Hozir bu xavf yo'q, chunki matching HECH QACHON v3 tokenidan foydalanmaydi (§4); matching v3'ga o'tsa, bu kafolat yo'qoladi.
2. **Offset moslashtirish murakkab.** v2'da har token o'zining original belgi oralig'iga ega (`matching.tokenize()`). Agar matching stem qilingan tokenlarda ishlasa, "stem" ko'pincha so'zning FAQAT bir qismi (masalan "kitob" "kitoblarni"dan) — tegishli original oraliq endi noaniq: butun so'z "kitoblarni"ni belgilashi kerakmi yoki faqat "kitob" qismini? Bu yangi, hali yechilmagan dizayn savoli, mavjud `span()` funksiyasi buni hal qila olmaydi o'zgarishsiz.
3. **Yolg'on musbat (false positive) xavfi oshadi.** §1.4'dagi ingliz so'zlari (`learning`→`lear`) misoli ko'rsatadiki, stem qilingan shaklda solishtirish TURLI manbalardagi TASODIFAN bir xil stemga tushgan so'zlarni "mos" deb belgilashi mumkin — bu hozir B1'dagi FP=0 natijasini buzishi mumkin. Qaysi fayllar: `backend/comparison/matching.py` (`compare()`, `runs()`), testlar: `test_comparison.py`, `test_corpus_integration.py`dagi barcha offset-bog'liq testlar qayta ko'rilishi kerak.
4. Qisqasi: **foyda (recall) bor, lekin narxi (xavfsizlik kafolatlari qayta qurilishi) hozircha baholanmagan.** Birinchi navbatda §2 nuqsonini tuzatish (oson — `query_windows()`ni original katta-kichik harfni saqlaydigan qilib qurish YOKI index tomonini ham oldindan casefold qilish, ikkisini bir xil qilish kifoya), keyin FAQAT RETRIEVAL darajasida foyda qolaversa ("v3 opt-in" hozirgi holatida), keyin GINA matching'ga ko'chirishni alohida loyihalashtirish kerak.

**(c) Agar retrieval darajasida delta nolga yaqin bo'lsa** — bu bizning holatimiz emas (§3'da aniq delta bor), lekin savol javobsiz qolmasin: eng past-ta'sir qoida — `stem_too_short` rad etilishi arzimas (0.3%, §1.3) — demak `MIN_STEM_LEN`ni pasaytirish deyarli hech narsa bermaydi. Eng ko'p ta'sir qiladigan parametr `MIN_WORD_LEN_TO_STRIP` (7 belgi, `too_short` 50.5%ni bloklaydi) — buni pasaytirish qamrovni sezilarli oshiradi, lekin bu ataylab tanlangan xavfsizlik chegarasi, raqam uni pasaytirishni OQLAMAYDI (chunki aynan shu chegara qisqa so'zlarni himoya qiladi — pasaytirish xavfsizlik-foyda almashinuvini o'zgartiradi, "bepul" emas).

## 6. Darvoza

162 backend testi (B bosqichidan o'zgarmagan — bu bosqich kod yozmadi). Determinizm `--repeat 2` bilan tasdiqlandi (pass1/pass2 bir xil). Hech qanday migratsiya, kod yoki test qo'shilmadi/o'zgartirilmadi — faqat shu hisobot va ikki CSV.
