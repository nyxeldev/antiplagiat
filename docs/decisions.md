# Mahsulot qarorlari

Bu fayl koddan ko'rinmaydigan yoki tarqoq joylashgan, lekin ataylab qabul qilingan mahsulot qarorlarini bitta joyda jamlaydi. Har bir yozuv — **qaror**, TODO yoki kelajakdagi reja emas; o'zgartirish uchun alohida muhokama va yangi yozuv kerak.

## 1. Korpus rol matritsasi

**2026-11-10 (roles-phase1) bilan eskirdi — [§18]ga qarang.** Quyida tasvirlangan 4 rolli model (`user`/`reviewer`/`corpus_manager`/`admin`) yangi 5 rolli modelga (`talaba`/`ustoz`/`kafedra_mudiri`/`admin`/`super_admin`) ko'chirildi; mantiq (kim nimani boshqaradi) o'zgarmadi, faqat nomlar va `super_admin` qo'shildi. Tarixiy band sifatida saqlanadi.

Korpus boshqaruvi (`/corpus/documents` va unga bog'liq yozish amallari) faqat `admin` va `corpus_manager` rollariga ochiq. Boshqa har qanday rol (`user`, `reviewer` — shu jumladan autentifikatsiyadan o'tgan, lekin bu ikki rolga tegishli bo'lmagan foydalanuvchi) uchun **403** qaytariladi.

Bu `backend/auth.py`dagi `require_corpus_manager()` funksiyasida majburlanadi (`CORPUS_MANAGEMENT_ROLES = {"admin", "corpus_manager"}`). Shaxsiy hisobotlarni solishtirish (`include_corpus` bayrog'i) esa bundan mustasno — u barcha autentifikatsiyadan o'tgan foydalanuvchilarga ochiq, chunki korpus bilan *solishtirish* korpusni *boshqarish* emas.

## 2. Korpus excerpt kafolati — jamlanish endi cheklangan

`backend/corpus.py`dagi `redact()` funksiyasi har bir solishtirish natijasini (`result`) saqlashdan oldin qayta ishlaydi: korpus manbasining to'liq matni hech qachon hisobotga yozilmaydi, faqat mos parcha (≤1200 belgi, `CORPUS_MATCH_CHARS`) va uning atrofidagi cheklangan kontekst (bitta hisobot uchun jami ≤20 000 belgi byudjet, `CORPUS_EXCERPT_BUDGET`) saqlanadi. Bu ikkisi — kontekst va bitta hisobotning byudjeti — **o'zgarmadi**.

**2026-11-09 (FAZA 3) — tuzatildi: foydalanuvchi x korpus hujjati bo'yicha jamlangan byudjet.** Avval (yuqoridagi, endi tarixiy band edi) bu byudjet faqat BITTA solishtirish chaqiruvi doirasida amal qilardi — har bir yangi `/compare` so'rovi o'z mustaqil 20 000 belgilik byudjetidan boshlanardi, demak ko'p sonli alohida so'rov orqali vaqt o'tishi bilan bir hujjatning katta qismini yig'ish MUMKIN edi. Endi `redact()`ga `user_id` uzatilganda (production yo'lida — `backend/comparison/api.py`dagi `with_corpus()` — har doim shunday), **mos parcha matni (match text, kontekst emas)** uchun qo'shimcha, DATABASE'da saqlangan, hisobotlar orasida TOZALANMAYDIGAN chegaralash ham ishlaydi:

- Jadval: `antiplagiat.corpus_excerpt_audit` (migratsiya 007) — foydalanuvchi, korpus hujjati, hisobot, **ko'rsatilgan belgi soni** (matnning o'zi EMAS), vaqt. `backend/corpus.py`dagi `_already_shown_chars()` shu jadvaldan foydalanuvchi + hujjat bo'yicha jami sarflangan belgini o'qiydi; `record_excerpt_disclosures()` yangi oshkoralikni yozadi (faqat hisobot saqlangandan KEYIN, chunki yozuv `report_id`ga bog'liq — `redact()` esa hisobot saqlanishidan OLDIN ishlaydi).
- Chegara formulasi (`corpus.py`dagi `per_document_budget()`): `clamp(0.15 × hujjat.char_count, 1200, 6000)`.
  - **Ulush — 15%:** haqiqiy tekshiruvchiga bir nechta haqiqiy sessiyada bir xil manbaga nisbatan bir necha alohida moslikni tasdiqlashga yetadi, lekin uzoq muddatda jamlanishni hujjatning kichik qismi bilan cheklaydi.
  - **Pastki chegara — 1200 (= `CORPUS_MATCH_CHARS`):** ulush o'zi YETARLI emas — qisqa hujjat uchun 15% bitta to'liq mos parchadan ham kichik bo'lib qolishi mumkin, bu esa hali HECH NARSA ko'rilmagan hujjatning ENG BIRINCHI so'rovida ham matnni yashirib, funksiyani foydasiz qilardi. Pastki chegara `CORPUS_MATCH_CHARS`ga teng qilib tanlangani uchun BIRINCHI hisobotning BIRINCHI moslik parchasi har doim butunlay ko'rinadi (qancha moslik topilgan bo'lishidan qat'i nazar, har bir moslik "butunlay ko'rinadi yoki umuman ko'rinmaydi" — qisman emas).
  - **Yuqori chegara — 6000 (= 5 × `CORPUS_MATCH_CHARS`):** ulushning o'zi YETARLI emas — uzun hujjat (masalan to'liq dissertatsiya, yuz minglab belgi) uchun 15% o'nlab minglab belgiga teng bo'lib qolardi, bu aynan yuqoridagi "katta qismini tiklash" xavfi. Qattiq yuqori chegara har qanday hujjat o'lchamidan qat'i nazar, bir foydalanuvchiga umrbod ko'rsatiladigan MAKSIMAL hajmni ~5 ta mos parcha bilan cheklaydi — bir necha aniq topilmani tasdiqlashga yetadi, haqiqiy maqolani qayta yig'ishga yetmaydi.
- **Qisqa hujjatlar — atayin qoldirilgan cheklov:** ~8000 belgidan qisqa hujjat uchun (15% < pastki chegara) pastki chegara ustunlik qiladi — demak qisqa hujjat NISBATAN ko'proq ochiladi (hatto butunlay ham bo'lishi mumkin bir necha mos parchada). Bu formula buni YECHMAYDI, ataylab — pastki chegara o'chirilsa birinchi moslik kafolati buziladi (yuqoridagi band). Hujjat sifatida qayd etilgan, yopiq emas.
- **Byudjet qoidalari:** byudjet HISOBOT YARATILGANDA sarflanadi (`with_corpus()` ichida, hisobot saqlanishidan oldin hisoblanadi, saqlangandan keyin yoziladi). Saqlangan hisobotni tarixdan qayta ochish (`backend/reports.py`dagi `get()`) saqlangan, ALLAQACHON qayta ishlangan snapshotni qaytaradi — `redact()` qayta chaqirilmaydi, demak qayta ochish byudjetni HECH QACHON qayta sarflamaydi. Byudjet tuganda moslik, foiz, manba nomi va joylashuvi ko'rinishda qoladi (`compare()`ning coverage hisob-kitobi `redact()`dan mustaqil) — faqat matn parchasi o'rniga `budget_exhausted`/`budget_exhausted_reason` beriladi (frontend: `frontend/app/report-view.tsx`dagi `CorpusExcerpt`, mavjud hisobot ekranida, yangi ekran emas). `metadata_only` hujjat umuman excerpt bermaydi — demak byudjet unga taalluqli emas (hech narsa sarflanmaydi, hech narsa yozilmaydi).
- **admin/corpus_manager — qaror:** bu byudjet ULARGA HAM, boshqa har qanday rolga o'xshab, aynan bir xil tartibda qo'llaniladi — `redact()` chaqiruvchining rolini bilmaydi, faqat `user_id`ni biladi. Sabab: korpusni BOSHQARISH huquqi uni CHEKSIZ KO'RISH huquqini avtomatik berishi shart emas — admin/corpus_manager allaqachon alohida, rol bilan cheklangan, redaksiyalanmagan yo'lga ega (`GET /corpus/documents/{id}`, moderatsiya uchun, `require_corpus_manager()`). Shu reader-facing, byudjet bilan himoyalangan solishtirish yo'lini ularga cheksiz qilish ortiqcha va keraksiz imtiyoz bo'lardi.
- **Saqlash muddati:** audit yozuvlari uchun ~12 oy tavsiya etiladi. **2026-11-09 (FAZA 4) yangilandi:** endi qo'lda ishga tushiriladigan `manage.py audit-cleanup` buyrug'i orqali amalga oshiriladi — [§16] va [docs/operations.md](operations.md) §4ga qarang (hamon avtomatik/cron emas, ataylab).

**2026-11-09 (FAZA 3) — qo'shildi: so'rov tezligi cheklovi.** `backend/rate_limit.py`dagi `enforce()` — foydalanuvchi boshiga, DATABASE'da saqlangan (migratsiya 007, `antiplagiat.rate_limit_counters`; server qayta ishga tushganda yo'qolmaydi), 1 daqiqalik qattiq oyna:
- `"compare"` doirasi (chegarasi 30/daqiqa): faqat `POST /compare?include_corpus=true` — `with_corpus()`ning birinchi qatorida tekshiriladi, chunki faqat shu yo'l korpus excerpt'ini ochishi mumkin; qo'lda ikkita fayl bilan oddiy solishtirish korpus matniga umuman tegmaydi va allaqachon `comparison/api.py`ning yagona-oqimli `gate` qulfi bilan serializatsiya qilingan.
- `"corpus"` doirasi (chegarasi 60/daqiqa): `backend/corpus_api.py`dagi HAR BIR endpoint (ro'yxatlash, taklif qilish, moderatsiya) — yengilroq amallar, haqiqiy foydalanuvchi tomonidan tabiiy ravishda ko'proq so'raladi.
- Chegaraga yetganda: aniq, muloyim xabar (`rate_limit.MESSAGE`) — "Juda ko'p so'rov yuborildi. Bir necha soniyadan so'ng qayta urinib ko'ring." — `ServiceError("rate_limited", ..., 429)` orqali, frontendning mavjud umumiy xato ko'rsatish yo'lida (`ApiError`) o'zgarishsiz ko'rinadi.

**Hali ham ochiq qolgan holatlar (ataylab, hujjatlashtirilgan):**
- Qisqa hujjatlar (yuqoridagi pastki chegara bandi) — nisbatan ko'proq ochiladi.
- Byudjet "butunlay ko'rinadi yoki umuman ko'rinmaydi" tartibida ishlaydi (bitta hisobotda bir nechta moslik bo'lsa, ulardan ayrimlari ko'rinishi, ayrimlari ko'rinmasligi mumkin — lekin HECH BIR moslik qisman kesilmaydi).
- Audit jurnali saqlash muddati avtomatik (cron) emas — faqat qo'lda ishga tushiriladigan buyruq ([§16]) sifatida amalga oshirilgan; operator uni unutib qo'yishi mumkin.

## 3. Benchmark metodologiyasi — ikkita qoida

**(a) Near-duplicate/parafraz sinov hujjatlari taqiqlanadi.** Agar sinov/benchmark hujjati korpus hujjatining deyarli to'liq nusxasi yoki unga juda yaqin parafraz bo'lsa va **mos kelmaydigan dum** qoldirmasa, mos parcha (`match`) ta'rifi bo'yicha korpus matnining deyarli barchasini qamrab olishi mumkin — bu kontekst sizishi emas (chunki mos parcha allaqachon tekshiruvchida mavjud), lekin natija "to'liq matn ko'rsatildi"ga o'xshab noto'g'ri talqin qilinishi mumkin. Shuning uchun benchmark hujjatlari korpusdan **qisman** o'xshash va undan **aniq farq qiluvchi** qism saqlanadigan qilib tuziladi. ([docs/architecture.md](architecture.md), §3)

**(b) Morfologik kategoriya — "sof almashtirish" majburiy.** `scripts/measure_morph_strength.py`dagi `pure_substitution` metrikasi — morfologik (faqat qo'shimchali) deb belgilangan so'rov uchun qat'iy, chegarasiz o'tish mezoni: butun so'rov bo'yicha `inserted_words == 0 VA deleted_words == 0` bo'lishi shart (hech qanday so'z qo'shilmagan yoki olib tashlanmagan — faqat mavjud so'zlarning qo'shimchasi o'zgargan). `suffix_changed_ratio`ning o'zi uchun chegara **yo'q**; past qiymat kategoriyaning halol qiyinligi sifatida qabul qilinadi, nuqson sifatida emas.

## 4. Test fixture naqshi — umumiy yordamchi `TestCase`dan meros olmaydi

`backend/tests/test_corpus_integration.py`dagi `CorpusFixture` sinfi bir nechta test sinfi (`CorpusDatabaseTests`, `CorpusComparisonTests` va h.k.) orasida umumiy `setUp`/yordamchi metodlarni ulashadi, lekin **o'zi `unittest.TestCase`dan meros olmaydi** — faqat mixin sifatida ishlatiladi (`class CorpusDatabaseTests(CorpusFixture, unittest.TestCase)`). Agar `CorpusFixture` o'zi `TestCase` bo'lganida, `unittest discover` uni alohida (bo'sh) test sinfi sifatida ham topgan bo'lardi va umumiy metodlar boshqa sinflarda qayta-qayta "test" sifatida hisoblanish xavfi tug'ilardi. Bu naqsh test sonini sun'iy oshirmaslik uchun ataylab tanlangan.

## 5. uz-latin-v3 — uch rejim: off / retrieval / retrieval+matching

**2026-10-18 holati (tarixiy):** `uz-latin-v3` faqat **nomzod manba tanlash** (retrieval) bosqichida ishlardi; matching hamon `uz-latin-v2`da edi. Bu `backend/tests/test_corpus_integration.py`dagi ikkita testda tasdiqlangan edi: `test_v3_column_is_populated_without_changing_original_text_or_offsets` ("uz-latin-v3 stays retrieval-only: proven, not claimed.") va `test_v3_retrieval_never_changes_what_the_comparison_highlights`. **Bu ikki test hamon mavjud va o'tadi** — ular hali ham `matching.compare()`ning DEFAULT chaqiruvi (parametrsiz, ya'ni "off"/"retrieval" rejimlari) uchun to'g'ri bo'lib qoladi.

**2026-11-03:** matching bosqichi endi ham (opt-in) v3'dan foydalanishi mumkin. Uchta rejim, API'ning `normalization` so'rov parametri orqali tanlanadi (`POST /compare?include_corpus=true&normalization=...`):

| Rejim | `normalization` qiymati | Retrieval (nomzod tanlash) | Matching (mos parcha belgilash) | Eski xulq? |
| --- | --- | --- | --- | --- |
| **off** | `"v2"` (default) | `fts` ustuni, uz-latin-v2 | `uz-latin-v2` tokenlari, aniq moslik | O'ZGARMAGAN |
| **retrieval** | `"v3"` | `fts_v3` ustuni, uz-latin-v3 stemmer | `uz-latin-v2` tokenlari (o'zgarmagan) | O'ZGARMAGAN (bu eski "v3" bayrog'ining o'zi) |
| **retrieval+matching** | `"v3-matching"` | `fts_v3` ustuni, uz-latin-v3 stemmer (xuddi "retrieval" kabi) | `uz-latin-v3`ga stem qilingan kalitlar (`backend/comparison/matching.py`, `match_keys()`/`morph_key()`) | **YANGI** |

Muhim: `"v2"` va `"v3"` qiymatlari **aynan eski ma'nosida** qoldi — eski so'rovlar bit-ma-bit bir xil natija beradi (`backend/tests/test_comparison.py`dagi `test_matching_normalization_defaults_to_v2_unchanged` va butun mavjud 178 test shuni tasdiqlaydi). Faqat yangi `"v3-matching"` qiymati qo'shildi.

**Offset kafolati (o'zgarmas):** `morph_key()` faqat shingle algoritmining TENGLIK tekshiruvi uchun ishlatiladigan kalit — u hech qachon `span()`ga uzatilmaydi. Highlight va offset hamon tokenning ORIGINAL `start`/`end` oralig'idan olinadi (`matching.tokenize()`), demak foydalanuvchiga har doim TO'LIQ original so'z (qo'shimchasi bilan) ko'rsatiladi, hech qachon qisqartirilgan o'zak emas. Buni isbotlovchi testlar: `test_v3_matching_finds_morphological_variants_v2_misses` (`backend/tests/test_comparison.py`) va `test_v3_matching_finds_what_v3_retrieval_only_misses` (`backend/tests/test_corpus_integration.py`, to'liq API orqali, korpus bilan).

**Foiz semantikasi:** `retrieval+matching` rejimida hisoblangan `coverage_percent` boshqa siyosat ostida: `parameters.algorithm_version = "lexical-shingle-v2"` va `parameters.normalization_version = "uz-latin-v3"` (mavjud `"lexical-shingle-v1"`/`"uz-latin-v2"` yorliqlari qatorida, `backend/reports.py`ning `algorithm_version`/`normalization_version` ustunlarida saqlanadi — CHECK constraint yo'q, migratsiya kerak emas). Saqlangan ESKI hisobot snapshotlari o'zgarmaydi va qayta hisoblanmaydi (faqat yangi so'rovlar yangi qiymat oladi). Foydalanuvchiga ko'rinadigan matnda (`result["limitations"]`) bu rejim aniq "tajriba" deb belgilangan.

**O'lchov natijasi** (`benchmarks/corpus-v2/`, `scripts/eval_retrieval.py --repeat 2` bilan determinizm tasdiqlangan; to'liq hisobot: [docs/benchmarks/uz-morph-v3-matching.md](benchmarks/uz-morph-v3-matching.md)): morfologik so'rovlarning ENG QIYIN qatlamida (suffix% >= 35%, **n=5 — indikativ, statistik jihatdan aniq o'lchov emas**) matching recall **0.1802 (off) -> 0.5238 (retrieval+matching)**, past qatlamda (suffix% < 20%, n=10) **0.7234 -> 0.8545**. **Eslatma:** `morphological`/`paraphrase` kategoriyalarida ground truth `__FULL_TEXT__` bo'lgani uchun precision u yerda TA'RIFGA KO'RA har doim 1.0 (o'lchangan natija emas — uz-morph-v3-matching.md §3). Yolg'on musbat riskini haqiqatan cheklaydigan dalillar: `hard_negative`+`unrelated`da (n=14, aniq ground truth bilan) yolg'on musbat soni 0, uchta rejimning hech birida; `partial`/`quoted` va `verbatim`ning aniq-snippet so'rovlarida uch rejim natijasi (precision HAM, recall HAM) aynan bir xil. Shu asosda qabul mezoni ("yolg'on musbat 0dan oshmasin") qondirilgan. **TASDIQLANGAN (2026-11-04, uz-morph-v3-matching.md §4):** `morphological` uchun TOKEN DARAJASIDAGI haqiqiy ground truth (`scripts/measure_morph_strength.py::token_level_ground_truth()`, `__FULL_TEXT__`ni manifest.json'da o'chirmasdan, alohida `morph_strength.json`da) bilan qayta hisoblangan HAQIQIY precision/recall/F1: off/retrieval 1.0000/0.5576/0.6670, retrieval+matching 1.0000/0.7561/0.8460 — ortiqcha belgilangan tokenlar 0 ta, 15/15 so'rovning hech birida. Demak `morphological`dagi recall o'sishi haqiqiy tokenlarni topish evaziga, yolg'on musbatlar hisobiga EMAS.

**Foiz TAQQOSLANMASLIK qoidasi:** bir xil hujjat-manba juftligi uchun `retrieval+matching`da hisoblangan `coverage_percent` `off`/`retrieval`dagidan ODATDA YUQORIROQ (o'lchangan: `morphological` kategoriyada o'rtacha +19.59pp, eng ko'p +41.03pp; boshqa to'rt ijobiy kategoriyada farq yo'q — qarang uz-morph-v3-matching.md §6). Bu "yaxshiroq natija" emas — BOSHQA siyosat (`lexical-shingle-v2`) bilan hisoblangan boshqa metrika. **Uch rejimning foizlari bir-biri bilan hech qachon "oldin/keyin" sifatida solishtirilmaydi**; har bir rejimning foizi faqat o'zi ichida (bir xil rejimda qayta tekshirish) ma'noli.

**UI qarori (2026-11-04):** o'lchov shuni ko'rsatdi — `retrieval` rejimining o'zi (sof, matching'siz) amalda foydasiz: eng qiyin qatlamda ham matching recall atigi +0.018 ko'tariladi (foydalanuvchiga ko'rinadigan highlight deyarli o'zgarmaydi). Shu sababli `frontend/app/comparison.tsx`dagi mavjud "O'zbekcha qo'shimchalarni hisobga olish (tajriba)" belgisi `normalization=v3`dan `normalization=v3-matching`ga o'tkazildi — foydalanuvchiga haqiqiy, o'lchangan foyda beradigan rejimga. **Uch rejim API/konfiguratsiyada (`normalization=v2`/`v3`/`v3-matching`) hamon saqlanadi** — faqat frontend checkbox'ining maqsadi o'zgardi, shuning uchun sof retrieval-only o'lchovlar (masalan uz-morph-v3.md) istalgan vaqt qayta ishlab chiqarilishi mumkin. Brauzerda tekshirishda aniqlandi: `comparison.tsx`dagi bu o'zgarish yolg'iz yetarli emas edi — `frontend/lib/proxy.ts`ning query-param oq ro'yxati hali `normalization === "v3"`ni tekshirardi, `"v3-matching"`ni jim tashlab yuborardi, natijada backend har doim standart `v2`da ishlardi. `proxy.ts`ning oq ro'yxatiga `v3-matching` ham qo'shilib tuzatildi (batafsil: uz-morph-v3-matching.md §7); bu matching algoritmining o'ziga tegmaydi, faqat frontend proxy qatlamiga oid edi.

## 6. Dependency yangilanmaydi qoidasining istisnosi — critical xavfsizlik patchlari

Loyihaning odatdagi siyosati: dependency versiyalari ataylab o'zgartirilmaguncha barqaror ushlab turiladi (`backend/requirements.txt`, `frontend/package.json`/`package-lock.json` — versiyalar bu fayllarda, `AGENTS.md`da emas). **Istisno:** paket ta'minotchisi tomonidan e'lon qilingan **critical** og'irlikdagi, aniq GHSA/CVE raqamiga ega va **non-major** (breaking o'zgarishsiz patch/minor) tuzatish mavjud bo'lsa, u alohida, tor qamrovli PR orqali — faqat shu bitta paket uchun — yangilanishi mumkin.

**Sana:** 2026-11-02. **Sabab:** `next` paketi `16.4.0` versiyasida uchta e'lon qilingan zaiflik bor edi:
- [GHSA-2464-fhr4-w9xw](https://github.com/advisories/GHSA-2464-fhr4-w9xw) — critical, Image Optimization API orqali autentifikatsiyasiz RCE (SVG fayllar orqali).
- [GHSA-673q-mjm6-r5xr](https://github.com/advisories/GHSA-673q-mjm6-r5xr) — critical, `use cache` funksiyalari typed array qaytarganda autentifikatsiyasiz RCE.
- [GHSA-p3m5-59mp-jv5r](https://github.com/advisories/GHSA-p3m5-59mp-jv5r) — high, Server Actions orqali DoS.

Uchalasi ham `>=16.0.0 <=16.4.0` oralig'ida, `16.4.3`da (patch, major emas) tuzatilgan. `next` `16.4.3`ga yangilandi (faqat shu paket; boshqa hech bir dependency o'zgartirilmadi) va `next.config.ts`ga `images.unoptimized: true` qo'shildi (ilova `next/image`dan umuman foydalanmaydi — grep bilan tasdiqlangan — shuning uchun Image Optimization endpoint'ining o'zini o'chirish GHSA-2464 hujum yuzasini versiyadan qat'i nazar yopadi).

## 7. Frontend test freymvorki (vitest/jest) ataylab qo'shilmadi

Bu **kelajakdagi ish** sifatida qayd etiladi, kamchilik sifatida emas: hozircha loyihada frontend uchun hech qanday unit-test freymvorki yo'q, va bu holat ataylab davom ettirilmoqda.

**Sabab:** 2026-11-02 kuni real brauzer tekshiruvi (Claude Browser orqali qo'lda) ikkita haqiqiy nuqsonni topdi, ikkalasi ham unit test bilan emas, balki real render/klik oqimi bilan aniqlangan:
- Mobil tortma (drawer) orqa foni (backdrop) uning o'zidan baland z-index'ga ega edi — bu barcha navigatsiya havolalari va chiqish tugmasini bosilmaydigan qilib qo'ygan edi (`frontend/app/shell/shell.module.css`).
- "Solishtirish" tugmasi faqat qo'lda manba fayl yuklanganda faollashar edi, hatto "ichki korpus" belgisi yoqilgan bo'lsa ham — bu korpus MVP'sining asosiy ssenariysini (hujjatni FAQAT korpusga qarshi tekshirish) butunlay bloklagan (`frontend/app/comparison.tsx`).

Ikkalasi ham komponent darajasidagi mock'langan unit test bilan emas, balki haqiqiy DOM/CSS tartibini yoki to'liq forma holatini talab qiladigan sinov bilan topilgan — izolyatsiyalangan unit test ularni ko'pincha o'tkazib yuborgan bo'lardi.

Tugma mantig'ining o'zi (hujjat + manba/korpus kombinatsiyasi) backend tomonda testlar bilan kafolatlangan: `no_sources` (400) rad etilishi va "faqat korpus" muvaffaqiyati `backend/tests/test_comparison.py` va `backend/tests/test_corpus_integration.py`da 4 ta test bilan qoplangan (ko'ring [docs/decisions.md] — bu fayl, keyingi PR).

Yangi dependency/infratuzilma (vitest yoki jest, jsdom, React Testing Library, CI integratsiyasi) qo'shish uchun o'lchangan, hozirgi loyiha hajmiga mutanosib zarurat hali yo'q. Ehtiyoj kuchayganda (masalan, komponent soni yoki regressiya chastotasi oshganda) qayta ko'rib chiqiladi.

## 8. CI'dagi Postgres integratsiya testlari — ildiz sababi topildi va tuzatildi

Oldin (§ ushbu fayl, 1-nashr) `.github/workflows/ci.yml`dagi 3 ta Postgres-integratsiya moduli (`test_corpus_integration`, `test_migration_diagnostics`, `test_review_regressions`) `continue-on-error: true` bilan eslatib qo'yilgan edi, chunki `backend/tests/postgres_fixture.py` o'zining `initdb`/`pg_ctl` subprocess chiqishini `DEVNULL`ga yuborar, haqiqiy xato sababi hech qachon ko'rinmas edi.

**2026-11-02:** `postgres_fixture.py` endi subprocess chiqishini (fayl orqali, PIPE emas — Windows'da `pg_ctl start`ning uzoq ishlaydigan `postgres` bolasi pipe handle'ni meros olib, tozalashni abadiy bloklashi mumkinligi amalda tasdiqlandi) tutib, xato bo'lganda `server.log` mazmuni bilan birga xabarga qo'shadi. Test mantig'i o'zgarmadi.

Shu diagnostika bilan CI'da haqiqiy xato olindi:
```
pg_ctl: could not start server
FATAL: could not create lock file "/var/run/postgresql/.s.PGSQL.<port>.lock": Permission denied
```

**Sabab:** Debian'ning `postgresql` apt-paketi `/var/run/postgresql`ni standart `unix_socket_directories` sifatida o'rnatadi, u `postgres` tizim hisobiga tegishli; GitHub Actions'ning imtiyozsiz `runner` foydalanuvchisi u yerga socket lock-fayl yoza olmaydi. Bu fixture hech qachon Unix socket orqali emas, faqat TCP (`127.0.0.1`) orqali ulanadi — demak bu **fundamental CI cheklovi emas**, shunchaki o'chirilishi kerak bo'lgan standart sozlama edi.

**Tuzatish:** `pg_ctl start`ga `-o` orqali `unix_socket_directories=""` uzatildi — postgres Unix socket yaratishga umuman urinmaydi. Haqiqiy CI yurgizishda tasdiqlandi: barcha 43 ta integratsiya testi `continue-on-error`siz chinakamiga o'tadi (11.2 soniya). `continue-on-error` workflow faylidan olib tashlandi — endi bu testlar PR'ni backend job'ining qolgan qismi kabi haqiqatan himoya qiladi.

## 9. `MIN_WORD_LEN_TO_STRIP` — eski ablatsiya tavsiyasi qayta ko'rib chiqildi (qiymat hamon 7)

**Eski asos (2026-10-18, [docs/benchmarks/uz-morph-v3-d2-ablation.md](benchmarks/uz-morph-v3-d2-ablation.md)):** 7/6/5 qiymatlari retrieval darajasida (fts_v3, barcha besh qatlamda/to'rt metrikada) **bit-baytiga bir xil** natija berdi — 7dan pastga tushishning o'lchangan foydasi NOL edi, lekin chet so'zlarni (en/ru) noto'g'ri qirqish soni monoton oshdi (11→13→14). Shu sababli **7da qoldirish** tavsiya qilindi va qiymat o'zgartirilmadi.

**YANGILANGAN ASOS (2026-11-04, [uz-morph-v3-matching.md §9](benchmarks/uz-morph-v3-matching.md)):** eski ablatsiya ikki bo'shliqqa ega edi — morfologik precision o'shanda `__FULL_TEXT__` ta'rifi bilan tautologik 1.0 edi (haqiqiy emas), va matching hamon `uz-latin-v2`da edi (`retrieval+matching` rejimi hali yo'q edi), demak chegara matching darajasida UMUMAN sinalmagan edi. `scripts/measure_strip_threshold_ablation.py` bu ikkisini to'ldirib qayta o'lchadi: `retrieval+matching` rejimida, §4'dagi HAQIQIY token-darajasidagi ground truth bilan, 7/6/5 uchun morfologik recall **monoton o'sadi** (0.7561 → 0.7883 → 0.8015), precision/FP narxisiz (ortiqcha belgilangan tokenlar va hard_negative+unrelated yolg'on musbatlar — bu safar HAQIQIY retrieval+matching orqali sinalgan — uchta qiymatda ham 0). Chet so'z noto'g'ri qirqilishi hamon monoton o'sadi (3→5→6 noyob so'z), lekin kichik.

**Yangi tavsiya: 6** (marginal foyda-narx nisbati 7→6'da 6→5'dan yaxshi: 0.0161 vs 0.0132 recall/xato-so'z — batafsil uz-morph-v3-matching.md §9). **Qiymat hamon O'ZGARTIRILMAGAN** — `backend/comparison/uz_latin_v3.py`dagi `MIN_WORD_LEN_TO_STRIP = 7` qoladi; bu faqat yangilangan tavsiya, amalga oshirish alohida qaror.

`MIN_STEM_LEN` (4 belgi) bu ablatsiyaga kiritilmadi — uning o'z o'lchovi hali qilinmagan.

## 10. Korpus birlamchi tekshiruv oqimi — qo'lda manba ixtiyoriy qolishi

**Qaror (2026-11-05):** `frontend/app/comparison.tsx`dagi `includeCorpus` bayrog'ining boshlang'ich qiymati `false`dan `true`ga o'zgartirildi — yangi tekshiruv ekranini ochganda ichki korpus bo'yicha solishtirish **default yoqilgan**. Qo'lda manba fayl yuklash **olib tashlanmadi**: u endi yig'ilgan (collapsed) "Qo'shimcha manba qo'shish (qo'lda yuklash)" bo'limida (`motion.tsx`dagi `Disclosure` orqali) joylashgan, kerak bo'lsa ochiladi.

**Sabab:** [1-qaror]ning rol matritsasi va bu PRdagi korpus boshqaruv ekrani (`frontend/app/corpus/page.tsx`) bilan admin/`corpus_manager` endi korpusni haqiqiy hujjatlar bilan to'ldira oladi — demak korpus endigacha "qo'shimcha tekshirish" emas, **birlamchi** solishtirish manbasi bo'lishi mumkin. Qo'lda yuklash butunlay olib tashlanmadi, chunki: (a) korpusga hali kiritilmagan hujjatlar bilan solishtirish ehtiyoji qoladi, (b) foydalanuvchi ikkalasini ham birga ishlatishi mumkin bo'lishi kerak.

**O'zgarmagan xulq (mavjud testlar bilan kafolatlangan):** ikkalasi ham (korpus VA qo'lda manba) o'chirilgan holatda solishtirish faol emas — bu mavjud `no_sources` mantig'i (`!document || (!sources.length && !includeCorpus)` sharti `comparison.tsx`da o'zgarmadi, faqat boshlang'ich qiymati). Backend tomonidagi `no_sources` rad etilishi va "faqat korpus" muvaffaqiyati sinovlari ([7-qaror]da eslatilgan `backend/tests/test_comparison.py` va `backend/tests/test_corpus_integration.py`) **o'zgartirilmadi** — bu ularning aynan shu sharti tasdiqlagan default-holatdan mustaqil ekanini ko'rsatadi. O'zgarish faqat frontenddagi boshlang'ich holat va UI tartibi; backend `/compare` so'rovi, uning validatsiyasi yoki mavjud hisob-kitob o'zgarmadi.

## 11. O'zbek kirill yozuvini qo'llab-quvvatlash — ataylab qilinmagan ish

Bu **qaror**, bajarilmagan ish yoki kamchilik emas: tizim faqat lotin yozuvidagi o'zbek matnini qayta ishlaydi (`backend/comparison/uz_latin_v3.py` va undan oldingi normalizatsiya qatlamlari), kirill transliteratsiyasi yoki kirill uchun alohida normalizatsiya yo'li qo'shilmaydi.

**Sabab:** korpusga kiritiladigan akademik arxiv (BMI, dissertatsiya, kurs ishi, maqola) deyarli to'liq lotin yozuvida yozilgan — kirill hujjatlar amaliyotda uchramaydi. Kirill qo'llab-quvvatlashni qo'shish (alifbo aniqlash, transliteratsiya yoki ikkinchi normalizatsiya/`fts` yo'li, va bularni sinovdan o'tkazish) real foydalanish hajmiga nisbatan o'lchanmagan murakkablik qo'shardi.

Ehtiyoj paydo bo'lsa (masalan, kirill yozuvidagi hujjatlar korpusga haqiqatan kiritilsa boshlansa), bu qaror qayta ko'rib chiqiladi — bu yopiq eshik emas, hozirgi arxiv tarkibiga asoslangan ustuvorlik.

## 12. Ustoz uchun yangi rol yaratilmadi — mavjud `user` roli, endi admin bergan bayroq bilan

**2026-11-10 (roles-phase1) bilan qisman eskirdi — [§18]ga qarang.** `user` roli endi mavjud emas: ustozlar uchun ishlatilgan "user + `can_submit_to_corpus` bayrog'i" naqshi endi **alohida `ustoz` roli** (yangi, kengroq emas, 5 rolli modelning bir qismi) + O'SHA BAYROQNING O'ZI (o'zgarmagan, hamon `admin`ga tegishli) ko'rinishida davom etadi. Quyidagi bahs (nega alohida bayroq kerak edi) **hamon kuchda** — faqat "`user`" o'rniga "`ustoz`" o'qing; bayroq endi ham ortiqcha emas, chunki `ustoz` roliga eski `reviewer` roli ham ko'chirilgan (taklif huquqisiz) — [§18]da batafsil.

**Qaror (2026-11-08, FAZA 2da qabul qilingan, 2026-11-08da bayroq bilan qattiqlashtirilgan):** FAZA 2 (korpusga hujjat taklif qilish va moderatsiya) uchun bazada yangi `teacher` roli **qo'shilmadi**. O'rniga mavjud `user` roli "ustoz" vazifasini bajarishga **nomzod** hisoblanadi, lekin bu avtomatik huquq EMAS: `antiplagiat.users.can_submit_to_corpus` bayrog'i (migratsiya 006, default `false`) har bir `user`-rolidagi akkaunt uchun alohida, admin tomonidan yoqiladi.

**Sabab (rol tanlovi uchun, FAZA 2):** loyihaning MAQSADi — tizimni "kafedra ustozlariga" ochish — shuni ko'rsatadiki, bu platformaning oddiy (admin/corpus_manager/reviewer bo'lmagan) foydalanuvchilari **aynan** ustozlarning o'zi, alohida ikkinchi populyatsiya emas. Yangi rol qo'shish `migration 001`dagi `users.role` CHECK cheklovini (checksummli, o'zgartirib bo'lmaydigan) kengaytiruvchi yangi migratsiya talab qilardi — bazaviy jadvalga tegish, faqat nomlash aniqligi uchun. Mavjud `user` rolidan foydalanish bu xavfni butunlay olib tashlaydi.

**Sabab (bayrog'i uchun, keyinroq qattiqlashtirish):** "har bir `user` akkaunti avtomatik ravishda korpusga taklif qila oladi" — bu haqiqiy ustozlar bilan bir xil `user` rolini baham ko'radigan har qanday oddiy ro'yxatdan o'tgan akkauntga ham taklif huquqini beradi, chunki bu platformada `user` roli ko'proq auditoriyani qamrab oladi. Shu sabab alohida ruxsat darajasi kerak: `can_submit_to_corpus` — bazaga tegishli, lekin `users.role` CHECK invariantiga tegmaydigan minimal qo'shimcha.

**Oqibat:** admin/corpus_manager o'zining to'g'ridan-to'g'ri (`/corpus/documents`, moderatsiyasiz, `review_status='approved'`) yo'lini saqlab qoladi va `require_teacher()`da bayroqdan mustaqil ravishda o'tadi. Oddiy `user` esa faqat `can_submit_to_corpus=true` bo'lgandagina `/corpus/submissions` orqali, har doim `review_status='pending'` bilan, taklif qila oladi; bayroqsiz `user` va `reviewer` — 403. Bayroqni yoqish/o'chirish faqat `admin` uchun ochiq (`require_admin()`, `POST /users/{user_id}/corpus-submission-access`, `backend/auth.py`dagi `set_corpus_submission_access()`). Kelajakda haqiqiy ikkinchi populyatsiya (masalan, talabalar) paydo bo'lsa, bu qaror qayta ko'rib chiqiladi.

## 13. Parol siyosati — production uchun qaytarildi (12 belgi + sodda parollar taqiqi)

**Qaror (2026-11-09, FAZA 4):** `backend/manage.py`dagi `MIN_PASSWORD_CHARS` 2026-10dagi lokal sinov yengilligi (4) dan **12**ga qaytarildi, va ikki eng oddiy, taxmin qilinishi eng oson parol shakli taqiqlandi: faqat raqamlardan iborat parol, va login bilan bir xil (katta-kichik harfga sezgir bo'lmagan) parol (`backend/manage.py`dagi `weak_password_reason()`).

**Nega 12, nega 8 emas:** NIST 800-63B kabi umumiy tavsiyalar 8 belgini minimal chegara deb oladi, lekin bu loyihada (a) parol murakkabligi qoidalari (katta harf/belgi talabi) YO'Q — faqat uzunlik va ikki sodda shaklni rad etish bilan cheklanadi, va (b) lug'at/tashqi xizmat tekshiruvi ATAYLAB qo'shilmadi (topshiriq shartiga ko'ra). Shu ikki yengillikni qoplash uchun minimal uzunlik 8dan yuqoriroq tanlandi: 12 belgi, murakkablik qoidasisiz ham, brute-force qiyinligini sezilarli oshiradi (argon2id xeshlash bilan birga — `backend/auth.py`dagi `HASHER`, `time_cost=3, memory_cost=65536`) va parafraza/qo'shma so'z uslubidagi uzun-lekin-sodda parollarga imkon qoldiradi.

**Lug'at/tashqi xizmat ATAYLAB yo'q:** topshiriq shartiga ko'ra qo'shilmadi; faqat ikkita ARIFMETIK/TO'G'RIDAN-TO'G'RI tekshiriladigan shakl (faqat raqam, login bilan bir xil) rad etiladi — bular tashqi ma'lumotga ehtiyoj sezmaydi.

**Mavjud akkauntlar buzilmagan:** yangi qoida FAQAT `manage.py`dagi `create_user()` (yagona parol o'rnatish yo'li — hozircha o'z-o'zidan ro'yxatdan o'tish yoki parol o'zgartirish API endpointi yo'q) orqali yangi parol yaratishda tekshiriladi. `backend/auth.py`dagi `login()` o'zi parol uzunligini UMUMAN tekshirmaydi — demak 2026-10dagi yengil qoida ostida yaratilgan har qanday mavjud, 4 belgili parolli akkaunt eski parol bilan kirishda davom etadi (sinov: `backend/tests/test_auth.py`dagi `test_legacy_short_password_is_not_rejected_by_login`). Kelajakda o'z-o'zidan parol o'zgartirish funksiyasi qo'shilsa, u ayni shu `create_user()`dagi tekshiruvni (`MIN_PASSWORD_CHARS`/`weak_password_reason()`) qayta ishlatishi kerak, alohida nusxa emas.

**Testlar:** `backend/tests/test_auth.py`dagi `test_password_length_policy_is_enforced_before_any_connection` (mavjud, chegaralar), `test_create_user_rejects_trivially_simple_passwords` (yangi, ikki sodda shakl), `test_legacy_short_password_is_not_rejected_by_login` (yangi, orqaga moslik).

## 14. Ishga tushirishda majburiy konfiguratsiya tekshiruvi — fail-fast

**Qaror (2026-11-09, FAZA 4):** `backend/main.py`ga FastAPI `lifespan` qo'shildi — `require_startup_configuration()` server ISHGA TUSHISHDAN OLDIN `ANTIPLAGIAT_DB_*` besh o'zgaruvchisi (`persistence.settings()`) va `ANTIPLAGIAT_PUBLIC_ORIGIN` (`auth.public_origin()`) ni tekshiradi; birortasi yo'q/noto'g'ri bo'lsa, `uvicorn` butunlay ishga TUSHMAYDI (aniq, mavjud Uzbek xato xabari bilan — yangi xabar emas, so'rov vaqtida ko'rsatiladigan xabarning o'zi).

**Avvalgi holat bilan farq:** avval protsess bu o'zgaruvchilarsiz ham MUVAFFAQIYATLI ishga tushardi (`/health` 200 qaytarardi), faqat DB kerak bo'lgan har bir so'rov alohida 503 bilan muvaffaqiyatsiz bo'lardi. Bu "xavfsiz bo'lmagan default" emas edi (hech qanday default yo'q — `settings()` bo'sh qiymatda doim xato qaytaradi), lekin "noto'g'ri sozlangan holatda sukut bilan qabul so'rovlarni kutib turish" production uchun yetarli emas: endi noto'g'ri sozlangan protsess UMUMAN ishga tushmaydi, monitoring/orchestration darajasida darhol ko'rinadi.

**Test ta'siri yo'qligi tasdiqlandi:** `backend/tests/test_review_regressions.py`dagi `ApiContractTests` `app(scope, receive, send)`ni to'g'ridan-to'g'ri, ASGI `"lifespan"` scope'isiz chaqiradi — demak bu test hech qachon `lifespan`ni ishga tushirmaydi; `backend/tests/test_readiness.py` esa `main.ready()`/`main.health()`ni oddiy funksiya sifatida chaqiradi, ASGI orqali emas. Ikkisi ham o'zgarishsiz o'tadi (barcha 224 test, shu jumladan FAZA 4ning yangi 5 testi, o'tadi).

**Kodda qolgan boshqa defaultlar auditi:** `ANTIPLAGIAT_PUBLIC_ORIGIN` (`backend/auth.py`) va `ANTIPLAGIAT_API_URL` (`frontend/lib/proxy.ts`) — ikkisi ham yo'q bo'lganda faqat `127.0.0.1` manziliga tushadi, **xavfsiz** deb baholandi (tizim arxitektura bo'yicha allaqachon faqat lokal interfeysga cheklangan — `auth.guard()`, `proxy.ts`). Boshqa hech qanday `os.environ.get(..., "...")`/`process.env.X ?? "..."` shaklidagi default butun repo bo'yicha topilmadi, `MIN_PASSWORD_CHARS`dan tashqari (§13da tuzatildi).

**`.env.example`:** mavjud, lekin ushbu agent sessiyasining o'z xavfsizlik sozlamalari `.env*` naqshiga mos har qanday faylni o'qish YOKI yozishni butunlay rad etadi (vosita darajasida, loyiha qoidasi emas) — shuning uchun uning to'liqligini men o'zim tasdiqlay yoki tahrirlay olmadim. To'liq tavsiya etilgan tarkib [docs/operations.md](operations.md) §1da — operator buni qo'lda solishtiradi/joylashtiradi.

## 15. Sessiya cookie — Secure bayrog'i allaqachon konfiguratsiyaga bog'liq edi; muddat/uzaytirish qoidasi endi hujjatlashtirildi

**Tekshirildi (2026-11-09, FAZA 4):** `backend/accounts_api.py`dagi `login()`/`logout()` cookie o'rnatishda `secure=auth.public_origin().startswith("https://")` ALLAQACHON ishlatadi — ya'ni lokal HTTP origin uchun `Secure` o'chiq, HTTPS origin uchun yoqiq, **kod o'zgarishi talab qilinmadi**. `HttpOnly`/`SameSite=strict`/`Path=/` o'zgarmas. Bu `backend/tests/test_auth.py`dagi `CookieTests.test_https_secure_cookie_and_no_token_in_body` bilan allaqachon sinalgan edi.

**Muddat va uzaytirish qoidasi (endi hujjatlashtirildi, kod o'zgarmadi):** `backend/auth.py`dagi `SESSION_SECONDS = 8 * 60 * 60` — sessiya **qattiq 8 soat**dan keyin tugaydi (`sessions.expires_at`, bazada). **Uzaytirish (sliding renewal) YO'Q** — foydalanuvchi faol bo'lsa ham, sessiya yaratilgan vaqtdan aniq 8 soatdan keyin qayta kirish talab qilinadi; yagona uzaytirish yo'li — yangi `login()` chaqiruvi (`old_token` orqali eski sessiya o'chiriladi, yangisi yaratiladi). Bu ataylab qoldirilgan: sliding renewal qo'shish `require_user()`ning HAR bir chaqiruvida qo'shimcha UPDATE talab qilardi (performance) va "token qancha uzoq amal qiladi" chegarasini noaniqlashtirardi; qattiq 8 soat soddaroq va auditga qulayroq.

## 16. Audit jurnali saqlash muddati — endi qo'lda ishga tushiriladigan buyruq bilan amalga oshirildi

**Qaror (2026-11-09, FAZA 4):** [§2]da tavsiya etilgan ~12 oylik saqlash muddati endi `backend/manage.py audit-cleanup --older-than-days 365` orqali amalga oshiriladi (`backend/corpus.py`dagi `purge_excerpt_audit()`). **Cron/Task Scheduler talab qilinmaydi** — topshiriq shartiga ko'ra, buyruq operator tomonidan ongli ravishda, qo'lda ishga tushiriladi.

**Nega privilegiyali hisob bilan:** runtime roli (`antiplagiat_app`) bu jadvalda ATAYLAB faqat SELECT+INSERT huquqiga ega (append-only — [§2]), DELETE huquqi yo'q. Shuning uchun `purge_excerpt_audit()` `manage.py`ning migratsiya uchun ishlatiladigan xuddi shu interaktiv, privilegiyali hisob oqimidan (`prompt_database()`) foydalanadi — ilova o'z-o'zidan audit tarixini o'chira olmasligi ataylab saqlanadi.

**Testlar (real PostgreSQL, `backend/tests/test_corpus_integration.py`dagi `AuditRetentionTests`):** eski yozuv o'chirilishi va yangisi saqlanib qolishi, runtime rolining bu amalni bajara OLMASLIGI (append-only invariant), va noto'g'ri (manfiy/satr) parametrning rad etilishi.

## 17. FAZA 4dan keyin — qabul qilingan cheklov va keyingi muhandislik bosqichining ikki sharti

**Qaror (2026-11-10):** FAZA 4 (§13–§16) yakunlangach, kod tomondan boshqa kutilayotgan ish yo'q. Ikki ochiq nuqta ataylab **hozir hal qilinmaydi**, backlog sifatida qayd etiladi:

- **`--workers 1` cheklovi** ([docs/operations.md](operations.md) §5): backend gorizontal kengaymaydi, chunki ichki qulflar (`comparison/api.py`dagi `gate`, `corpus_api.py`dagi `gate`, `auth.py`dagi `login_gate`) BITTA Python protsessi doirasida ishlaydi — bir nechta uvicorn worker ularni baham ko'rmaydi. Kafedra miqyosi uchun yetarli; butun akademiyaga ochilganda solishtirish navbatini protsessdan tashqariga (masalan DB-navbat yoki tashqi queue) chiqarish kerak bo'ladi.
- **Testlardagi asyncio diagnostika qatori** (`backend.tests.test_review_regressions.ApiContractTests`ni ishga tushirishda ba'zan ko'rinadigan "Executing ... took N seconds" qatori): natija hamon `OK`, bloker emas — odatda yopilmagan event loop/tugallanmagan taskdan chiqadi. Hozir kuzatiladi, amalga oshirilmaydi; agar qator ko'payib borsa yoki test to'plami sekinlashsa, o'shanda tekshiriladi.

**Keyingi muhandislik bosqichi quyidagi ikki shartdan BIRI yuzaga kelganda boshlanadi, oldin emas:**
1. Korpus 100 hujjatdan oshganda — nomzod limiti (`corpus.py`dagi `DEFAULT_CANDIDATES`/`MAX_CANDIDATES`) qayta o'lchanadi.
2. Server aniqlanganda — HTTPS va haqiqiy joylashtirish topshirig'i (`docs/operations.md`dagi muhitdan mustaqil ko'rsatmalar o'rniga aniq muhitga moslashtirilgan reja).

## 18. roles-phase1 — 5 rolli model, kafedra skeleti va `can_submit_to_corpus` qoldi

**Qaror (2026-11-10):** eski 4 rolli model (`user`, `reviewer`, `corpus_manager`, `admin`) **5 rolli modelga** ko'chirildi: `talaba`, `ustoz`, `kafedra_mudiri`, `admin`, `super_admin` (`backend/auth.py`dagi `ROLES`). Bu **faqat nomlash va bir yangi rolning (`super_admin`) qo'shilishi** — birorta ham mavjud ruxsat mantig'i o'zgartirilmadi (pastdagi jadvalga qarang).

**Migratsiya (`backend/migrations/008_role_model_v1.sql`) — aniq xaritalash, qaytarib bo'lmaydigan ravishda qo'llanildi:**

| Eski holat | Yangi rol | Izoh |
| --- | --- | --- |
| `role='admin'` | `admin` | o'zgarmadi |
| `role='corpus_manager'` | `kafedra_mudiri` | nomlash o'zgardi, huquq o'zgarmadi |
| `role='reviewer'` | `ustoz` | nomlash o'zgardi; `can_submit_to_corpus` bayrog'i **false** holicha qoladi (reviewer hech qachon taklif huquqiga ega bo'lmagan) |
| `role='user'`, `can_submit_to_corpus=true` | `ustoz` | bayrog'i **true** holicha qoladi |
| `role='user'`, `can_submit_to_corpus=false` | `talaba` | yangi standart rol |
| — (hech qachon avtomatik) | `super_admin` | faqat `manage.py assign-role <login> super_admin` orqali, qo'lda |

Bu xaritalash haqiqiy legacy-shakldagi qatorlar ustida `backend/tests/test_role_migration.py`da (yangi, 4 test) tasdiqlangan: besh sintetik akkaunt (har bir eski rol/bayroq kombinatsiyasi uchun bittadan) migratsiyadan **oldin** xom SQL bilan kiritiladi, so'ng migratsiya 008 haqiqatan ishga tushiriladi va (a) xaritalash aniq yuqoridagi jadvalga mos kelishi, (b) `super_admin`ning hech qachon o'zi paydo bo'lmasligi, (c) barcha besh akkaunt eski parol bilan kira olishi, (d) eski imtiyozlarning saqlanib qolgani (masalan eski `corpus_manager` — endi `kafedra_mudiri` — hamon `require_corpus_manager()`dan o'tadi) tekshiriladi.

**Haqiqiy dev bazadagi natija (2026-11-10, shu sessiyada qo'lda ishga tushirilgan `migrate` orqali tasdiqlangan):** `korpus_admin` (`corpus_manager` → `kafedra_mudiri`) va `teacher_test` (`user`+bayrog'i true → `ustoz`, bayrog'i true) brauzerda haligacha o'zining avvalgi ekranlari bilan kira oldi — pastdagi "Brauzer tekshiruvi" bandiga qarang.

**Yangi 5 ta rolning har biri uchun endpoint × rol ruxsat matritsasi:** `backend/tests/test_role_permissions.py` (yangi) — kod ichidan (xotiradan emas) chiqarilgan **15 ta** himoyalangan endpoint (`accounts_api.py`, `corpus_api.py`, `comparison/api.py`), har biri o'zining `backend.auth` guard funksiyasi bilan belgilangan. Har bir endpoint × har bir rol (15 × 5 = 75) + `ustoz` roli uchun ikkita `can_submit_to_corpus` holati har bir endpointda qayta tekshiriladi (bayrogning uchta bayroqqa e'tibor bermaydigan guard uchun ahamiyatsizligini ham tasdiqlash uchun, faqat `require_teacher` uchun emas) — jami **90** kombinatsiya — plyus har bir endpoint uchun anonim chaqiruvning 401 bilan rad etilishi (**15** ta alohida tekshiruv). Fayl ichidagi izoh kelajakda yangi endpoint qo'shilganda bu ro'yxatni ham kengaytirish zarurligini eslatadi.

**Kafedra (department) — faqat skelet, FAZA 2 emas:** yangi `antiplagiat.kafedra` jadvali va `users.kafedra_id` (nullable FK) + CLI (`manage.py kafedra-add/kafedra-list/kafedra-assign`) qo'shildi, lekin **kafedra darajasida ko'rinish cheklovi hali ishlamaydi** — `kafedra_mudiri` hamon BARCHA korpusni ko'radi, faqat o'z kafedrasinikini emas. Bu ataylab, topshiriq shartiga ko'ra: departament bo'yicha skoplash **keyingi bosqich** (phase 2) ishi, bu PR doirasiga kirmaydi.

**`can_submit_to_corpus` ortiqchami? — YO'Q, saqlab qolindi.** Bayroq rol bilan bir xil narsani takrorlamaydi: `ustoz` roli endi ikkita sifat jihatidan har xil kelib chiqishli kichik populyatsiyani birlashtiradi — (a) eski haqiqiy `user`+bayrog'i-true akkauntlar (taklif huquqi bor) va (b) eski `reviewer` akkauntlar, endi `ustoz`ga ko'chirilgan, lekin bayrog'i **false** (taklif huquqi yo'q, hech qachon bo'lmagan). Agar bayroq olib tashlanib, faqat `role == "ustoz"` tekshirilganda, barcha eski `reviewer` akkauntlar birdaniga korpusga taklif huquqiga ega bo'lib qolardi — bu migratsiyaning o'zi ataylab oldini olgan narsa. Demak bayroq `ustoz` rolidan **mustaqil, admin tomonidan alohida boshqariladigan** ruxsat qatlami bo'lib qolaveradi (`require_teacher()`: `role in CORPUS_MANAGEMENT_ROLES OR (role == TEACHER_SUBMISSION_ROLE AND can_submit_to_corpus)`); yangi yaratilgan `ustoz` akkaunt ham standart holatda bayrog'i `false` bilan boshlanadi (`manage.py create-user`, migratsiya 006dagi ustun defaulti o'zgarmagan) — "ustoz" bo'lish o'zi avtomatik taklif huquqi bermaydi, buni `admin` alohida yoqishi kerak.

**Frontend:** faqat nom almashtirish, yangi ekran yo'q — `frontend/app/shell/AppShell.tsx` (`CORPUS_MANAGEMENT_ROLES`, nav-item sharti), `frontend/app/corpus/page.tsx` (`allowed` sharti) va `frontend/app/corpus/submit/page.tsx` (`allowed` sharti) yangilandi.

**Brauzer tekshiruvi (2026-11-10, Claude Browser orqali, haqiqiy ishga tushirilgan frontend+backend ustida):** `talaba` (`roles_phase1_talaba`) — faqat "Yangi tekshiruv"/"Tekshiruvlar tarixi" ko'rinadi; `ustoz` (`teacher_test`) — qo'shimcha "Korpusga hujjat taklif qilish" ko'rinadi, korpus boshqaruvi yo'q; `kafedra_mudiri` (`korpus_admin`) — "Korpus boshqaruvi" ko'rinadi, taklif-qilish yo'q; `admin` (`roles_phase1_admin`) — xuddi `kafedra_mudiri` kabi "Korpus boshqaruvi" ko'rinadi. `super_admin` brauzerda alohida tekshirilmadi — kod yo'lida `admin` bilan farqsiz (`ADMIN_ROLES = {"admin", "super_admin"}`), bu `test_role_permissions.py`da avtomatik qoplangan.

**Testlar:** to'liq to'plam `224 → 230` ga o'sdi (2 yangi fayl: `test_role_permissions.py` — 2 test/90+15 tekshiruv, `test_role_migration.py` — 4 test); barcha 230 test o'tadi.

---

*Eslatma: ushbu fayl faqat mahsulot/arxitektura qarorlarini qayd etadi. Agent ish uslubi, kodlash konventsiyalari va lokal muhit ko'rsatmalari repo tarkibiga kirmaydi (`.gitignore`). Operatsion tartiblar (zaxira/tiklash, loglar, production ishga tushirish) uchun [docs/operations.md](operations.md) qarang.*
