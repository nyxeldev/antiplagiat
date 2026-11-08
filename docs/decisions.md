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

## 12. Ustoz uchun yangi rol yaratilmadi — mavjud `user` roli ishlatildi

**Qaror (2026-11-08):** FAZA 2 (korpusga hujjat taklif qilish va moderatsiya) uchun bazada yangi `teacher` roli **qo'shilmadi**. O'rniga mavjud `user` roli "ustoz" vazifasini bajaradi: `backend/auth.py`dagi yangi `require_teacher()` shunchaki `role == "user"`ni talab qiladi, `TEACHER_SUBMISSION_ROLE` konstantasi orqali.

**Sabab:** loyihaning MAQSADi — tizimni "kafedra ustozlariga" ochish — shuni ko'rsatadiki, bu platformaning oddiy (admin/corpus_manager/reviewer bo'lmagan) foydalanuvchilari **aynan** ustozlarning o'zi, alohida ikkinchi populyatsiya emas. Yangi rol qo'shish `migration 001`dagi `users.role` CHECK cheklovini (checksummli, o'zgartirib bo'lmaydigan) kengaytiruvchi yangi migratsiya talab qilardi — bazaviy jadvalga tegish, faqat nomlash aniqligi uchun. Mavjud `user` rolidan foydalanish bu xavfni butunlay olib tashlaydi va "mavjud user roli — o'zing asosla" variantini to'g'ridan-to'g'ri qondiradi.

**Oqibat:** admin/corpus_manager o'zining to'g'ridan-to'g'ri (`/corpus/documents`, moderatsiyasiz, `review_status='approved'`) yo'lini saqlab qoladi; oddiy `user` esa faqat yangi `/corpus/submissions` orqali, har doim `review_status='pending'` bilan, taklif qila oladi. Kelajakda haqiqiy ikkinchi populyatsiya (masalan, talabalar) paydo bo'lsa, bu qaror qayta ko'rib chiqiladi.

---

*Eslatma: ushbu fayl faqat mahsulot/arxitektura qarorlarini qayd etadi. Agent ish uslubi, kodlash konventsiyalari va lokal muhit ko'rsatmalari repo tarkibiga kirmaydi (`.gitignore`).*
