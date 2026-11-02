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

---

*Eslatma: ushbu fayl faqat mahsulot/arxitektura qarorlarini qayd etadi. Agent ish uslubi, kodlash konventsiyalari va lokal muhit ko'rsatmalari repo tarkibiga kirmaydi (`.gitignore`).*
