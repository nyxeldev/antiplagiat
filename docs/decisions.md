# Mahsulot qarorlari

Bu fayl koddan ko'rinmaydigan yoki tarqoq joylashgan, lekin ataylab qabul qilingan mahsulot qarorlarini bitta joyda jamlaydi. Har bir yozuv — **qaror**, TODO yoki kelajakdagi reja emas; o'zgartirish uchun alohida muhokama va yangi yozuv kerak.

## 1. Korpus rol matritsasi

Korpus boshqaruvi (`/corpus/documents` va unga bog'liq yozish amallari) faqat `admin` va `corpus_manager` rollariga ochiq. Boshqa har qanday rol (`user`, `reviewer` — shu jumladan autentifikatsiyadan o'tgan, lekin bu ikki rolga tegishli bo'lmagan foydalanuvchi) uchun **403** qaytariladi.

Bu `backend/auth.py`dagi `require_corpus_manager()` funksiyasida majburlanadi (`CORPUS_MANAGEMENT_ROLES = {"admin", "corpus_manager"}`). Shaxsiy hisobotlarni solishtirish (`include_corpus` bayrog'i) esa bundan mustasno — u barcha autentifikatsiyadan o'tgan foydalanuvchilarga ochiq, chunki korpus bilan *solishtirish* korpusni *boshqarish* emas.

## 2. Korpus excerpt kafolati — doirasi va ma'lum cheklovi

`backend/corpus.py`dagi `redact()` funksiyasi har bir solishtirish natijasini (`result`) saqlashdan oldin qayta ishlaydi: korpus manbasining to'liq matni hech qachon hisobotga yozilmaydi, faqat mos parcha (≤1200 belgi) va uning atrofidagi cheklangan kontekst (bitta hisobot uchun jami ≤20 000 belgi byudjet, `CORPUS_EXCERPT_BUDGET`) saqlanadi.

**Muhim chegara:** bu byudjet faqat **bitta solishtirish chaqiruvi (bitta hisobot) doirasida** amal qiladi. Agar bir foydalanuvchi bir xil korpus hujjatiga nisbatan **bir nechta alohida so'rov** yuborsa, har bir so'rov o'zining mustaqil byudjetidan foydalanadi — so'rovlar orasida jamlangan (cumulative) chegaralash **yo'q**. Nazariy jihatdan, ko'p sonli maqsadli so'rovlar orqali vaqt o'tishi bilan korpus hujjatining katta qismini qayta tiklash mumkin.

**Kelajakdagi mumkin bo'lgan yechimlar** (hali amalga oshirilmagan):
- Foydalanuvchi + korpus hujjati juftligi bo'yicha jamlangan (cumulative) excerpt hisoblagichi
- Bir xil hujjatga qayta-qayta so'rov yuborishni rate-limit qilish
- Umumiy ko'rsatilgan belgilar soniga audit log

## 3. Benchmark metodologiyasi — ikkita qoida

**(a) Near-duplicate/parafraz sinov hujjatlari taqiqlanadi.** Agar sinov/benchmark hujjati korpus hujjatining deyarli to'liq nusxasi yoki unga juda yaqin parafraz bo'lsa va **mos kelmaydigan dum** qoldirmasa, mos parcha (`match`) ta'rifi bo'yicha korpus matnining deyarli barchasini qamrab olishi mumkin — bu kontekst sizishi emas (chunki mos parcha allaqachon tekshiruvchida mavjud), lekin natija "to'liq matn ko'rsatildi"ga o'xshab noto'g'ri talqin qilinishi mumkin. Shuning uchun benchmark hujjatlari korpusdan **qisman** o'xshash va undan **aniq farq qiluvchi** qism saqlanadigan qilib tuziladi. ([docs/architecture.md](architecture.md), §3)

**(b) Morfologik kategoriya — "sof almashtirish" majburiy.** `scripts/measure_morph_strength.py`dagi `pure_substitution` metrikasi — morfologik (faqat qo'shimchali) deb belgilangan so'rov uchun qat'iy, chegarasiz o'tish mezoni: butun so'rov bo'yicha `inserted_words == 0 VA deleted_words == 0` bo'lishi shart (hech qanday so'z qo'shilmagan yoki olib tashlanmagan — faqat mavjud so'zlarning qo'shimchasi o'zgargan). `suffix_changed_ratio`ning o'zi uchun chegara **yo'q**; past qiymat kategoriyaning halol qiyinligi sifatida qabul qilinadi, nuqson sifatida emas.

## 4. Test fixture naqshi — umumiy yordamchi `TestCase`dan meros olmaydi

`backend/tests/test_corpus_integration.py`dagi `CorpusFixture` sinfi bir nechta test sinfi (`CorpusDatabaseTests`, `CorpusComparisonTests` va h.k.) orasida umumiy `setUp`/yordamchi metodlarni ulashadi, lekin **o'zi `unittest.TestCase`dan meros olmaydi** — faqat mixin sifatida ishlatiladi (`class CorpusDatabaseTests(CorpusFixture, unittest.TestCase)`). Agar `CorpusFixture` o'zi `TestCase` bo'lganida, `unittest discover` uni alohida (bo'sh) test sinfi sifatida ham topgan bo'lardi va umumiy metodlar boshqa sinflarda qayta-qayta "test" sifatida hisoblanish xavfi tug'ilardi. Bu naqsh test sonini sun'iy oshirmaslik uchun ataylab tanlangan.

## 5. uz-latin-v3 — faqat retrieval, matching hamon v2

`uz-latin-v3` (qoidaga asoslangan o'zbekcha suffix-stripping) faqat **nomzod manba tanlash** (retrieval) bosqichida ishlaydi. Yakuniy mos parchani belgilash, offsetlarni hisoblash va foiz chiqarish — bularning barchasi hamon `backend/comparison/matching.py`dagi o'zgarmagan `uz-latin-v2` normalizatsiyasida bajariladi (`NORMALIZATION_VERSION = "uz-latin-v2"`, kodda qattiq yozilgan, v3'ga bog'liq emas).

Bu `backend/tests/test_corpus_integration.py`dagi ikkita testda aniq tasdiqlangan:
- `test_v3_column_is_populated_without_changing_original_text_or_offsets` — "uz-latin-v3 stays retrieval-only: proven, not claimed."
- `test_v3_retrieval_never_changes_what_the_comparison_highlights`

---

*Eslatma: ushbu fayl faqat mahsulot/arxitektura qarorlarini qayd etadi. Agent ish uslubi, kodlash konventsiyalari va lokal muhit ko'rsatmalari repo tarkibiga kirmaydi (`.gitignore`).*
