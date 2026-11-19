# Islom akademiyasi uchun antiplagiat tizimi

O‘zbekiston xalqaro islom akademiyasining ruxsat bilan to‘plangan ilmiy hujjatlari va foydalanish huquqi tekshirilgan tashqi manbalar bilan matn o‘xshashligini aniqlash loyihasi.

**Holat:** lokal autentifikatsiya va shaxsiy tekshiruvlar tarixi mavjud. CLI orqali yaratilgan hisob login/parol bilan kiradi, TXT/DOCX/PDF solishtiradi, PostgreSQL’da saqlangan hisobotni tarixdan ochadi yoki tasdiqlab o‘chiradi va logout qiladi. Har bir backend so‘rovi session va egalikni tekshiradi. `GET /health` va `GET /ready` saqlangan. Bu lokal ishlab chiqish bosqichi; akademiya piloti uchun tayyor tizim emas.

**Hujjat versiyasi:** 0.4 · **Sana:** 2026-11-05.

## Maqsad va chegaralar

Mos parchalar, ularning manbalari va tekshiruv qamrovini ko‘rsatadigan, BMI doirasida takrorlanuvchi tajribalar bilan baholanadigan platforma yaratish. O‘xshashlik foizi plagiatning avtomatik isboti emas. Yakuniy xulosani vakolatli inson beradi.

Butun internet, barcha ilmiy bazalar yoki yopiq nashrlar qamrab olinishi va’da qilinmaydi. Metama’lumot, annotatsiya, havola va amalda tahlil qilingan to‘liq matn alohida hisobga olinadi.

## Hujjatlar

| Fayl | Mazmun |
| --- | --- |
| [docs/requirements.md](docs/requirements.md) | Funksiyalar, rollar, maxfiylik va qabul mezonlari |
| [docs/architecture.md](docs/architecture.md) | Komponentlar, ma’lumotlar oqimi, algoritmlar va tashqi manbalar |
| [docs/roadmap.md](docs/roadmap.md) | Bosqichlar, tekshirish shartlari va BMI tajribalari |
| [docs/decisions.md](docs/decisions.md) | Koddan ko'rinmaydigan mahsulot qarorlari (rol matritsasi, korpus excerpt chegarasi, benchmark metodologiyasi) |

## Dastlabki texnologiyalar

Next.js + TypeScript; Python + FastAPI; PostgreSQL va uning full-text search imkoniyatlari. Sentence Transformers va pgvector semantik tajribalardan keyin qo‘shiladi. Redis, Celery va OpenSearch zarurati o‘lchovlar bilan asoslanadi. Git versiyalar nazorati uchun ishlatiladi. Frontend versiyalari quyida, backend paketlari `backend/requirements.txt` da qayd etilgan.

## Ishlash tartibi

1. Har safar bitta aniq amaliy qadam.
2. O‘zgartirishdan oldin mavjud fayllar va Git holatini o‘qish.
3. Koddan keyin tegishli test va kutiladigan natijani berish.
4. Natija tasdiqlanmaguncha keyingi bosqichga o‘tmaslik.
5. Buyruqlarni Windows PowerShell uchun, bajariladigan papkasini ko‘rsatib berish.
6. Muhitni tekshirmay dasturlarni qayta o‘rnatmaslik.
7. Kod, test ma’lumotlari va loglarga maxfiy kalit yoki haqiqiy maxfiy hujjat kiritmaslik.
8. Mantiqiy bosqichlarni alohida commit qilish; bir faylni ikki agentga nazoratsiz parallel tahrirlatmaslik.

Codex — amaliy o‘zgarishlar; Claude Code — mustaqil review va test; ChatGPT — qarorlar, izohlar va keyingi qadamlar. Rollar vazifaga ko‘ra o‘zgarishi mumkin.

## Hozirgi yagona qadam

Login, session va shaxsiy hisobot tarixi qo‘shildi. Bitta hujjat va 1–5 manba mavjud algoritm bilan solishtiriladi; muvaffaqiyatli hisobot saqlangandan keyin ko‘rsatiladi. PostgreSQL va migratsiya endi ushbu oqim uchun zarur. Doimiy umumiy korpus, indeks, tashqi qidiruv va semantik model qo‘shilmadi. `/health` backend holati, `/ready` esa avvalgidek faqat `SELECT 1` bilan DB ulanishi haqida ma’lumot beradi; sxema tayyorligini tasdiqlamaydi.

## Autentifikatsiya va shaxsiy tarix

Mavjud psycopg saqlandi; uch jadval va qisqa tranzaksiyalar uchun ORM qo‘shilmadi. `backend/migrations/001_accounts_reports.sql` users, sessions va reportsni yaratadi. `python -m backend.manage migrate` vakolatli **alohida** DB hisobini va yashirin parolni terminalda so‘raydi, migratsiya versiyasi/checksumini qayd qiladi va qayta ishga tushganda bajarilgan versiyani tekshiradi. Noma’lum yoki o‘zgartirilgan migratsiya rad etiladi; DDL va grants bir tranzaksiyada, advisory lock bilan bajariladi. Mavjud baza DROP yoki qayta yaratilmaydi.

`antiplagiat_app` mavjud, superuser va baza egasi bo‘lmagan runtime hisob bo‘lib qoladi. Migratsiya hisobi sxema yaratish va grants berishga vakolatli bo‘lishi kerak. Runtime uchun faqat schema USAGE, users SELECT, sessions SELECT/INSERT/DELETE, reports SELECT/INSERT hamda snapshot/deleted_at ustunlarini o‘chirish uchun UPDATE beriladi. UUID ishlatilgani uchun sequence huquqlari kerak emas. Runtime users/migratsiyalarni boshqarmaydi; report triggeri snapshotni tahrirlashni taqiqlaydi. Migratsiya CLI runtime hisobida ishlashdan bosh tortadi. Appdagi `admin` roli ham faqat o‘z hisobotlarini ko‘radi; `user/reviewer/corpus_manager/admin` maydoni kelajak modelini bildiradi, hozir rol boshqaruvi UI yoki qo‘shimcha huquqlar yo‘q.

Akkaunt yaratish: `python -m backend.manage create-user akademiya_user`; parol ikki marta yashirin kiritiladi, login 3–64 kichik lotin harfi/son/`_.-`. Parol uzunligi chegarasi `backend/manage.py` dagi `MIN_PASSWORD_CHARS`/`MAX_PASSWORD_CHARS` da; hozir lokal ishlab chiqish uchun egasi ko‘rsatmasi bilan 4–256 ga tushirilgan va pilotdan oldin qaytarib ko‘tarilishi kerak. Ommaviy ro‘yxatdan o‘tish, email va parolni tiklash yo‘q. Parol [argon2-cffi PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/howto.html) orqali Argon2id bilan hash qilinadi (64 MiB, 3 iteratsiya, parallelism 4). Runtime dependencylar aniq versiyalangan: argon2-cffi 25.1.0, argon2-cffi-bindings 26.1.0, cffi 2.1.1, pycparser 3.11; Windows/Python 3.14 da haqiqiy hash/verify va `pip check` tekshirildi.

Session — 32 tasodifiy baytdan opaque token; DBda faqat SHA-256 hashi va 8 soatlik muddat. Token URL/localStorage’da emas, Path=/, HttpOnly, SameSite=Strict cookie’da. HTTPS origin’da Secure, lokal HTTP’da Secure=false. Frontend va backenddagi `ANTIPLAGIAT_PUBLIC_ORIGIN` bir xil aniq qiymat bo‘lishi kerak; loopback HTTP standart `http://127.0.0.1:3000`. Boshqa host/portga o‘tilsa ikkala jarayon sozlanadi. HTTPS uchun lokal TLS terminatsiyasi kerak; frontend HTTPS va backend loopback HTTP bo‘lishi mumkin. Host/origin, maxsus header va backend loopback tekshiruvlari birga ishlaydi; CORS ochilmagan va forwarded IP ishonch manbai emas. O‘zgartiruvchi so‘rovda Origin majburiy. Logout DB sessionni o‘chiradi; backend restart sessionni bekor qilmaydi, uning DBdagi muddati saqlanadi.

Login xatosi mavjud/yo‘q akkaunt uchun bir xil; noma’lum akkauntda ham Argon2 verify bajariladi. Lokal limit: socket peer uchun 5 daqiqada 10 urinish (muvaffaqiyatlilari ham), bir paytda ko‘pi bilan 2 hash tekshiruvi. Next.js proxy orqali peer umumiy loopback bo‘lgani uchun foydalanuvchilar limitni bo‘lishadi. Hisoblagich process xotirasida, restartda tozalanadi; ko‘p worker yoki ommaviy xizmat uchun durable/distributed limit o‘rnini bosmaydi. Bitta backend worker bilan ishlating. Cookie/Authorization/parol/hisobot matni loglanmaydi; access log o‘chirilgan. DB xatosi maxfiy tafsilotsiz 503 beradi.

Hisobot UUID, egasi, yaratilgan vaqti, `lexical-shingle-v1` algoritmi, `uz-latin-v2` normalizatsiyasi va immutable JSONB snapshot bilan saqlanadi. Original binar fayllar vaqtinchalik; snapshotdagi **ajratilgan hujjat/manba matnlari ham maxfiy**. Ular internetga yuborilmaydi yoki umumiy korpusga qo‘shilmaydi. Tarix 20 tadan sahifalanadi; ID bilan olish/o‘chirish ham owner predicate bilan tekshiriladi, begona va yo‘q ID bir xil 404 beradi. Saqlash tranzaksiyasi commit qilinmaguncha `saved: true` qaytmaydi.

Bir fayl tanlovi uchun frontend bir xil `Idempotency-Key` UUIDni qayta urinishlarda saqlaydi; DBda `(owner_id, request_key)` unikalligi va fayl/nom/rol SHA-256 digesti duplicate hisobotni cheklaydi. Bir kalitga boshqa kontent — 409. Fayllarni qayta tanlash yoki “Yangi tekshiruv boshlash” yangi ish beradi; sahifa reloadida fayl tanlovi/kalit tiklanmaydi, tarmoq natijasi noaniq bo‘lsa avval tarixni tekshiring. O‘chirish tasdiq bilan snapshot matnini NULL qiladi; minimal tombstone (ID, egasi, sana, versiyalar, kalit va digest) qoladi, qayta yuborish 410 beradi va hisobot qayta ochilmaydi. Bu WAL/backup yoki diskdagi izlarning xavfsiz yo‘qotilishi emas; retention, backup va at-rest himoya siyosati real pilotdan oldin kelishiladi.

Lokal birinchi sozlash (parollarni argument yoki chatga yozmang):

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m backend.manage migrate
.\.venv\Scripts\python.exe -m backend.manage create-user akademiya_user
.\scripts\start_backend.ps1
# Backend ishlayotganida ikkinchi terminal:
Set-Location D:\antiplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

`start_backend.ps1` runtime sozlamalari va yashirin DB parolini terminalda so‘raydi, backendni foreground’da ishga tushiradi, tugaganda oldingi process env’ni tiklaydi. `.env` avtomatik o‘qilmaydi va haqiqiy maxfiy fayllarni ochish talab qilinmaydi. Migratsiya/account yaratish **mavjud foydalanuvchi bazasida agent tomonidan bajarilmadi**; haqiqiy DB testlari alohida disposable instansiyada bajariladi.

Migratsiya diagnostikasi: `python -m backend.manage migrate --check --diagnostic` parolni yashirin terminalda so‘raydi va **read-only** tranzaksiyada ulanish/preflightni bajaradi. DDL, grants va advisory lock bajarilmaydi. Runtime hisob/DB egasi siyosati, CREATE vakolati, SQL fayllari mavjudligi, amaldagi version/checksum va hali qo‘llanmagan boshlang‘ich migratsiyaning obyekt to‘qnashuvlari tekshiriladi. Sxemada 0 jadval bo‘lishi funksiyalar ham yo‘qligini anglatmaydi; mavjud obyekt avtomatik almashtirilmaydi.

`--diagnostic` faqat `stage=configuration/connect/preflight/migration/commit`, exception klassi, mavjud SQLSTATE va statik qadam/migratsiya identifikatorini chiqaradi. Parol, DSN, SQL/parametrlar yoki xom exception matni chiqarilmaydi; ommaviy HTTP xabari o‘zgarmaydi. `database_unavailable` avval ham connectiondan tashqari SQL bajarilishi, commit va `ValueError`ni yashirgan. Administrator diagnostikasi original klass/SQLSTATEni wrapperdan oldin ushlaydi; domain xatolari alohida qoladi. Oddiy migratsiya va grants faqat `--check` bo‘lmaganda bajariladi, atomic rollback/checksum himoyasi saqlanadi. Read-only PASS keyingi DDL/commitning mavjud klasterda muvaffaqiyatini kafolatlamaydi.

Tasdiqlangan alohida tuzatish: psycopg context managerida commit exception bo‘lsa closegacha yetilmaydi; persistence wrapper endi `finally` orqali ulanishni yopadi. Disposable PostgreSQL’da kechiktirilgan FK commit xatosi bilan takrorlanib, ulanish yopilishi va barcha DDL rollback bo‘lishi tekshirildi. Bu foydalanuvchining mavjud klasterdagi xatosi sababi deb tasdiqlanmagan. Ushbu diagnostika bosqichida 16 ta turli tegishli regressiya o‘tdi: 4 haqiqiy disposable PostgreSQL testi va 12 mock/unit testi (15 testlik to‘plam, so‘ng yangi SQL-fayl-yo‘qligi testi bilan 7 testlik tor unit yurishi). Katta HTTP to‘plami, frontend build, audit yoki paket o‘rnatish bajarilmadi; mavjud klasterga ulanilmadi. Diagnostika/regressiya buyruqlari: `python -m unittest backend.tests.test_migration_diagnostics backend.tests.test_review_regressions.ContractTests -v`.

## Lokal hujjat solishtirish

Mavjud `.venv` uchun yangilangan aniq dependency ro‘yxatini o‘rnatish (Node/npm yoki Python qayta o‘rnatilmaydi):

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Birinchi PowerShell oynasida backend:

```powershell
Set-Location D:\antiplagiat
.\scripts\start_backend.ps1
```

Ikkinchi PowerShell oynasida frontend:

```powershell
Set-Location D:\antiplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Brauzerda `http://127.0.0.1:3000` ni oching va CLI akkaunti bilan kiring. Bitta hujjat va 1–5 ta manba tanlang, **Solishtirish** ni bosing. Manba/parcha tanlang, original highlight va sahifa/paragrafni ko‘ring. “Tekshiruvlar tarixi” avvalgi snapshotni ochadi yoki tasdiqlab o‘chiradi; “Chiqish” sessionni bekor qiladi. Fayllarni qayta tanlash avvalgi ekrandagi hisobotni tozalaydi, saqlangan tarixga ta’sir qilmaydi. Serverlarni o‘z oynalarida `Ctrl+C` bilan to‘xtating. Faqat loopback manzilida, bitta backend worker bilan ishlating; internetga ochmang.

Brauzer shu origin’dagi `/api/compare` ga `FormData` yuboradi; Next.js server marshruti uni lokal FastAPI `POST /compare` ga oqimli uzatadi. Standart backend manzili `http://127.0.0.1:8000`. Boshqa lokal port kerak bo‘lsa, frontendni ishga tushirishdan oldin `$env:ANTIPLAGIAT_API_URL = 'http://127.0.0.1:8001'` belgilang. Bu server sozlamasi; DB sozlamalari brauzerga uzatilmaydi. CORS ochilmagan, tashqi backend manzili va redirectlar qabul qilinmaydi. Same-origin va maxsus header tekshiruvi tashqi saytdan oddiy forma yuborishni cheklaydi; bu autentifikatsiya o‘rnini bosmaydi.

**Formatlar:** UTF-8 TXT (BOM mumkin), DOCX asosiy matni va jadvallari, matn qatlamli PDF. TXTda bo‘sh bo‘lmagan satr paragraf hisoblanadi. DOCX header/footer, izohlar va rasmlar olinmaydi; sahifa raqami taxmin qilinmaydi. PDFda haqiqiy sahifa raqami beriladi, lekin murakkab maketdagi o‘qish tartibi noto‘g‘ri bo‘lishi mumkin. Shifrlangan, buzilgan, bo‘sh, kamida bitta matnsiz sahifali PDF yoki qo‘llanmaydigan fayl xato holatini qaytaradi; 0% hisobot yaratilmaydi. OCR yo‘q.

**Chegaralar:** har fayl 10 MiB, jami fayl baytlari 30 MiB; multipart overhead uchun qo‘shimcha 64 KiB. Har hujjat 200 000 ajratilgan belgi, 30 000 token va kamida 5 token bilan cheklangan; PDF ko‘pi bilan 200 sahifa. DOCX arxivi ochilganda jami 50 MiB, 1000 element, asosiy XML esa 8 MiB gacha. Bir vaqtda bitta tekshiruv; yuklash 60 soniya, parser va solishtirish jarayoni 30 soniya, xotira 512 MiB. Windows Job Object xotira/CPU chegaralari yoqilmasa qayta ishlash rad etiladi. Bir hujjat–manba juftiga 300 000 solishtirish amali, manbaga 500 mos parcha va hisobotga 12 MiB chegara bor. Chegaradan oshganda natija kesib olinmaydi: tushunarli xato qaytariladi.

**Hisoblash:** Unicode NFKC, registr (`casefold`) va o‘zbek apostrof variantlari normallashtiriladi; tokenlar orasidagi bo‘shliq/tinish belgilari moslikka to‘sqinlik qilmaydi. 5 ketma-ket tokenli shingles tengligi tekshiriladi va moslik ikki tomondagi teng tokenlar bo‘ylab uzaytiriladi. Minimal parcha — 5 token. Original parcha belgima-belgi teng bo‘lsa `exact`, aks holda `shingle` deb beriladi. Umumiy leksik qoplash = mos kelgan **noyob** tekshiriluvchi token pozitsiyalari / barcha tekshiriluvchi tokenlar × 100; manba foizlari qo‘shilmaydi. Original ajratilgan matn va token → original koordinata xaritasi saqlanadi. Offsetlar noldan boshlanadigan Unicode code point `[start, end)` oraliqlari; frontend UTF-16 farqini hisobga oladi.

**Normalizatsiya siyosati `uz-latin-v2`:** yuqoridagi NFKC/registr/apostrof qoidalariga qo‘shimcha ravishda faqat U+200B (ZWSP), U+00AD (soft hyphen), U+200C (ZWNJ) va U+FEFF belgilaridan iborat ketma-ketlik bevosita ikki lotin harfi orasida bo‘lsa solishtirish nusxasida tashlab ketiladi. Harf Unicode `L*` kategoriyasi va nomidagi `LATIN` bilan aniqlanadi; birikuvchi urg‘u orqali qo‘shni harfni qidirish yo‘q. Original ajratilgan matn va offsetlar o‘zgarmaydi. Barcha Cf/Mn belgilarini global o‘chirish yo‘q; arab va boshqa yozuvlardagi join-control belgilariga bu qoida qo‘llanmaydi. Matn boshi/oxiri, bo‘shliq yoki tinish belgisi yonidagi ketma-ketlik saqlanadi. Siyosat versiyasi hisobotning `parameters.normalization_version` maydonida, qoida qo‘llangani haqidagi ogohlantirish esa `limitations` va frontendda ko‘rinadi. Farqli original parchalar normallashtirilgan `shingle` deb belgilanadi.

ZWSP ba’zan haqiqiy so‘z chegarasi bo‘ladi: masalan, `bir<U+200B>ikki` bu evristikada `birikki` tokeniga aylanishi mumkin. Siyosat dastlabki o‘zbek lotin matnlari uchun tor evristika; barcha Unicode chetlab o‘tishlarini hal qilmaydi. Arab harakatlari yashirin olib tashlanmaydi va yangi arab normalizatsiyasi qo‘shilmagan. Unicode nomi `ARABIC` bo‘lgan `M*` belgilar hujjat yoki manbada aniqlansa, hisobotda **arab harakatlari bo‘yicha tokenizatsiya hali ishonchli emas; moslik va umumiy ko‘rsatkich ehtiyotkor talqin qilinishi kerak** degan ogohlantirish chiqadi. Arab tili to‘liq qo‘llab-quvvatlanishi tasdiqlanmagan.

**Cheklovlar:** o‘xshashlik plagiatning avtomatik isboti emas. Iqtibos/bibliografiya filtri yo‘q. “Moslik topilmadi” faqat yuklangan manbalar doirasida. Parafraz yoki semantik o‘xshashlik aniqlangan deb da’vo qilinmaydi; indekslash keyingi bosqich. Bitta manba yaroqsiz bo‘lsa butun so‘rov xato bilan tugaydi, yashirin qisman hisobot yo‘q.

Fayllar OS vaqtinchalik katalogida tasodifiy katalog va server bergan nomlar bilan ishlanadi. Foydalanuvchi fayl nomi disk yo‘li sifatida ishlatilmaydi. Muvaffaqiyat, parser/yuklash xatosi, timeout va saqlash xatosida katalog tozalanadi. Jarayon yoki kompyuter majburan o‘chirilgandagi disk qoldiqlarini yo‘qotish kafolatlanmaydi; bu xavfsiz o‘chirish tizimi emas. Hisobot PostgreSQL’dagi shaxsiy snapshot sifatida saqlanadi. Hujjatlar internetga yuborilmaydi; kod matn yoki maxfiy qiymatlarni loglamaydi. Parser worker stdout/stderr va logging chiqishlari bostirilgan. Hujjat matni React text node sifatida render qilinadi, HTML sifatida bajarilmaydi.

Yangi dependencylar (mavjudlari yangilanmagan):

| Paket | Versiya | Litsenziya va moslik |
| --- | --- | --- |
| [pypdf](https://pypi.org/project/pypdf/6.20.0/) | 6.20.0 | BSD-3-Clause; Python 3.14 klassifikatori, sof Python PDF parser |
| [defusedxml](https://pypi.org/project/defusedxml/0.7.1/) | 0.7.1 | PSFL; DOCX XMLda DTD/entity va tashqi resurslarni bloklash; 3.14 mosligi lokal test bilan tekshirildi |
| [python-multipart](https://pypi.org/project/python-multipart/0.0.32/) | 0.0.32 | Apache-2.0; Python 3.14 klassifikatori; hajmi chegaralangan oqimli yuklash |

DOCX uchun `zipfile` + `defusedxml` tanlandi: matn ajratishga yetarli va qo‘shimcha lxml dependency’si talab qilmaydi. Yangi parserlar Python 3.14.3 dagi mavjud muhitda sinovdan o‘tdi; yangilangan to‘liq requirements bilan toza muhitdan qayta o‘rnatish hali tekshirilmagan.

Tekshiruv buyruqlari:

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
Set-Location D:\antiplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe scripts/check_e2e.py
```

Autentifikatsiya/tarix bosqichida **39 ta unittest** va `pip check` o‘tgan. Auth DB/owner/CSRF/expiry va CLI yashirin parol testlarining bir qismi mock, Argon2 hash/verify va worker xotira/timeout testlari haqiqiy jarayonlarda. Comparison/readiness regressiyalari saqlangan: Unicode/apostrof/urg‘u, to‘rtta ko‘rinmas belgi/ketma-ketlik, boshqa yozuvlar, offsetlar, exact/shingle yorlig‘i, arab ogohlantirishi, kasrli timeout, parser/limit/cleanup. Mock testlar PostgreSQL testi sifatida hisoblanmaydi. CLI echo fallbackga o‘tishdan bosh tortadi; parolni yashirish imkoni bo‘lmasa kiritishni rad etadi.

`scripts/check_e2e.py` haqiqiy PostgreSQL 18 `initdb/pg_ctl` bilan **alohida disposable klaster** yaratadi; mavjud DB yoki maxfiy fayllarga murojaat qilmaydi. 64 ta HTTP tekshiruvi production frontend → FastAPI → worker → PostgreSQL oqimida o‘tdi: login generic xatolari, cookie/session hashi, anonymous/expiry/logout, owner isolation (B roli admin), CSRF, uch format, retry/conflict, tarix pagination, snapshot o‘zgarmasligi, runtime huquqlari, backend restart, DB saqlash xatosi va tozalash. Migratsiya replay/checksum/runtime denial ham haqiqiy DBda tekshiriladi. `/ready` bu testda 200, avvalgi konfiguratsiyasiz 503 holati readiness unit testida saqlanadi.

Ixtiyoriy browser testi uchun `.venv`ga `pip install -r scripts/test-requirements.txt`, so‘ng `python scripts/check_e2e.py --browser`. Test-only paketlar: Playwright 1.63.0, pyee 13.0.1, greenlet 3.5.6; runtime/npm dependencylariga qo‘shilmadi. Mavjud Edge headless rejimida 1440×1000 va 375×812 uchun login, solishtirish/retry, saqlangan highlight va ogohlantirishlar, tarix, owner denial, cancel/delete va logout o‘tdi; horizontal overflow tekshirildi. Bu avtomatik browser tekshiruvi; screenshot asosida qo‘lda vizual audit emas. Interactive browser helper `sandbox setup refresh` xatosi bilan ochilmadi. Testlar faqat o‘z server/brauzer/klasterini to‘xtatadi va vaqtinchalik kataloglarini olib tashlaydi. Haqiqiy foydalanuvchi bazasida migratsiya, HTTPS end-to-end, toza muhitdan o‘rnatish, ilmiy benchmark yoki murakkab real Word/PDF baholashi bajarilmadi. HTTPS Secure cookie mock response testi bilan tekshirildi.

## Ichki ilmiy korpus

Ruxsat asosida saqlanadigan ichki korpus. Korpusni **`admin` yoki `corpus_manager` roli** boshqaradi; oddiy foydalanuvchi korpus manbasidan to‘liq matnni olmaydi — faqat metama’lumot, mos parcha va har tomondan 200 belgigacha kontekst. **Korpus bo‘yicha tekshirish endi birlamchi oqim**: solishtirish formasidagi «Ichki korpus bo‘yicha tekshirish» belgisi default **yoqilgan**. Qo‘lda manba fayl yuklash olib tashlanmadi — u «Qo‘shimcha manba qo‘shish (qo‘lda yuklash)» nomi bilan yig‘ilgan (collapsed) bo‘limda qoladi, kerak bo‘lsa ochiladi va korpus bilan bir vaqtda ham ishlatilishi mumkin. Ikkalasi ham o‘chirilgan bo‘lsa (korpus belgisi olib tashlansa va qo‘lda manba yo‘q bo‘lsa) — mavjud `no_sources` mantig‘i bo‘yicha solishtirish faol bo‘lmaydi; bu xulq va unga oid backend testlari o‘zgarmadi (qaror va sabab: [docs/decisions.md, 10-band](docs/decisions.md)).

**Rol matritsasi** (koddagidek, [backend/auth.py](backend/auth.py)dagi `CORPUS_MANAGEMENT_ROLES`):

| Rol | `/corpus/documents` (qo‘shish/ro‘yxat/withdraw) | O‘z shaxsiy hisobotlari |
| --- | --- | --- |
| `admin` | 200 | 200 (faqat o‘ziniki) |
| `corpus_manager` | 200 | 200 (faqat o‘ziniki) |
| `user` | 403 | 200 (faqat o‘ziniki) |
| `reviewer` | 403 | 200 (faqat o‘ziniki) |
| login qilinmagan | 401 | 401 |

`corpus_manager` boshqa foydalanuvchilarning shaxsiy hisobotlarini ko‘rmaydi — korpus huquqi va hisobot egaligi butunlay mustaqil tekshiriladi.

Avval migratsiyani qo‘llang (`002_internal_corpus` qo‘shilgan):

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m backend.manage migrate --check
.\.venv\Scripts\python.exe -m backend.manage migrate
```

**Korpus boshqaruvchi hisob yaratish.** `--role` sifatida `admin` yoki `corpus_manager` beriladi — ikkalasi ham korpusni boshqaradi, farqi yo‘q (`corpus_manager` boshqa admin huquqlariga ega emas, faqat korpus uchun):

```powershell
.\.venv\Scripts\python.exe -m backend.manage create-user korpus_admin --role corpus_manager
```

Mavjud hisobga rolni berish uchun alohida CLI buyrug‘i yo‘q. Buni vakolatli DB hisobi bilan qo‘lda bajaring; parolni buyruq argumentiga yozmang (`role` qiymatini `admin` yoki `corpus_manager` qiling):

```powershell
.\.venv\Scripts\python.exe -c "import getpass, psycopg; psycopg.connect(host='127.0.0.1', port=5432, dbname='antiplagiat', user=input('Vakolatli DB hisobi: '), password=getpass.getpass('Parol: ')).execute(\"UPDATE antiplagiat.users SET role=%s WHERE username=%s\", (input('Rol (admin/corpus_manager): '), input('Login: '))).connection.commit()"
```

**Korpus buyruqlari.** Har biri vakolatli DB hisobini va parolni terminalda yashirin so‘raydi; `--as-user` `admin` yoki `corpus_manager` rolidagi hisobni ko‘rsatishi kerak:

```powershell
.\.venv\Scripts\python.exe -m backend.manage corpus-add D:\yol\hujjat.docx --as-user korpus_admin
.\.venv\Scripts\python.exe -m backend.manage corpus-list --status active
.\.venv\Scripts\python.exe -m backend.manage corpus-withdraw <hujjat-id>
```

`corpus-add` sarlavha, muallif, tur (`bmi/dissertatsiya/kurs_ishi/maqola/boshqa`), til belgisi, manba izohi, **ruxsat asosi** va yilni so‘raydi. Ruxsat asosi bo‘sh bo‘lsa hujjat saqlanmaydi. Fayl mavjud sandboxlangan parser orqali o‘qiladi; binar fayl saqlanmaydi, faqat ajratilgan matn, uning chunklari va `content_sha256` qoladi. Bir xil fayl faol holatda ikki marta kirmaydi. `corpus-withdraw` hujjatni qidiruvdan chiqaradi va uning matni hamda chunk matnlarini o‘chiradi; dalil uchun minimal yozuv qoladi (bu zaxira/WAL izlarini yo‘qotmaydi).

**Ommaviy (batch) kiritish.** Bir nechta faylni yoki papkani (ichidagi faqat `.txt`/`.docx`/`.pdf` fayllar, boshqa kengaytmalar jim o‘tkazib yuboriladi) bitta buyruq bilan kiritish uchun:

```powershell
.\.venv\Scripts\python.exe -m backend.manage corpus-add-batch D:\korpus\papka D:\yana-bitta-hujjat.pdf --as-user korpus_admin
```

Muallif, tur, til belgisi, manba izohi, **ruxsat asosi** va yil — bitta so‘rovda, **butun partiya uchun bir marta** so‘raladi (sarlavha har bir fayl nomidan avtomatik olinadi). Ruxsat asosi bo‘sh bo‘lsa, birorta ham fayl korpusga kirmasdan buyruq to‘xtaydi. Har bir fayl mustaqil ishlanadi — bittasi (noto‘g‘ri format, bo‘sh matn, skanerlangan PDF, dublikat va h.k.) bilan xato chiqsa, qolgan fayllar baribir davom etadi. Yakunda har bir fayl uchun natija qatordan-qator chiqadi (`QO‘SHILDI` / `DUBLIKAT` / `XATO`, sabab bilan) va umumiy son; birorta xato bo‘lsa buyruq exit code 1 bilan tugaydi (muvaffaqiyatli qo‘shilganlar baribir saqlangan bo‘ladi).

**Korpus boshqaruv HTTP endpointlari** (login bo‘lmaganda 401, `admin`/`corpus_manager` bo‘lmaganda 403):

| Endpoint | Vazifasi |
| --- | --- |
| `POST /corpus/documents` | multipart: `file` + `title`, `author_display`, `doc_type`, `year`, `language_hint`, `source_note`, `permission_basis` |
| `GET /corpus/documents?page=&status=` | `active`/`withdrawn`/`all` ro‘yxati |
| `POST /corpus/documents/{id}/withdraw` | Korpusdan chiqarish va matnni o‘chirish |

**Korpus boshqaruv UI sahifasi** (`/corpus`, faqat `admin`/`corpus_manager` uchun — `frontend/app/shell/AppShell.tsx`dagi navigatsiyada ham, sahifaning o‘zida ham boshqa rollarga ko‘rinmaydi): sahifalangan va holat bo‘yicha filtrlanadigan ro‘yxat, «Hujjat qo‘shish» dialogidagi forma (fayl + sarlavha/muallif/tur/yil/til/manba izohi/ruxsat asosi), hujjat tafsiloti va `ConfirmDialog` bilan korpusdan chiqarish. Yangi backend endpoint yoki kutubxona qo‘shilmadi — mavjud `/corpus/documents` endpointlari va mavjud design-system komponentlari (`Dialog`, `Dropzone`, `FileItem`, `Pagination` va h.k.) ishlatildi. CLI orqali boshqarish ham to‘liq saqlanadi — ikkisi bir xil endpointlardan foydalanadi. Nomzodlar PostgreSQL full-text qidiruvi bilan tanlanadi (`simple` konfiguratsiyasi, sababi [arxitekturada](docs/architecture.md)); bu reyting o‘xshashlik ko‘rsatkichi emas. Har tekshiruvda nomzodlar soni limit bilan cheklangan, shuning uchun hisobotda «limit tufayli korpusdagi barcha hujjatlar solishtirilmagan» izohi beriladi. Metama’lumot bilan amalda o‘qilgan to‘liq matn farqlanadi: korpus faqat ajratilgan to‘liq matn ustida ishlaydi va «butun internet» yoki to‘liq qamrov da’vosi yo‘q.

## Frontendni ishga tushirish va tekshirish

Auth review tuzatishlari: faqat `antiplagiat.users.users_username_key` buzilishi CLI’da “Bu login allaqachon band.” va exit code 1 beradi; `UsernameTakenError` DB wrapper tomonidan 503ga o‘ralmaydi. Boshqa DB xatolari sanitizatsiyalangan `database_unavailable` semantikasini saqlaydi. Hisobot INSERT natijasiz va keyingi retry ham None bo‘lsa `409/report_conflict` qaytadi, `200 null` emas. `request_conflict`, `report_deleted`, oddiy save va idempotent retry saqlangan.

Ushbu review uchun faqat `python -m unittest backend.tests.test_review_regressions backend.tests.test_comparison.LifecycleTests -v` — **10 test** o‘tdi: uch disposable PostgreSQL testi (haqiqiy CLI process/exit code, akkaunt o‘zgarmasligi, rollback/close, boshqa uniqueness xatosi, save/retry), besh yangi mock contract/ASGI testi va ikki mavjud cleanup testi. CLI terminal kiritishlari sun’iy stdin ma’lumotlari bilan almashtiriladi; parollar argumentga yoki kodga yozilmaydi. Mavjud foydalanuvchi DBsi, katta HTTP to‘plami, frontend build, yuklama va npm audit bu tor reviewda qayta tekshirilmadi; paket o‘rnatilmadi. Lokal login limiterining oldingi cheklovi o‘zgarmadi.

`frontend/` — Next.js App Router, TypeScript va ESLint asosidagi alohida npm loyiha. Tili `uz`; oddiy CSS/tizim shriftlari. Login/logout, yuklash/saqlash, kutish/xato, tarix va saqlangan hisobot, manba/parcha tanlash mavjud. Desktopda ikki, mobilda bir ustun. Tashqi font/CDN, Tailwind, UI kutubxonasi va React Compiler yo‘q. ESLint, TypeScript va production build o‘tdi.

Windows PowerShell 5.1, Node.js 24.21.0 va npm 12.0.2 bilan o‘rnatildi. Barqaror `create-next-app@16.4.0` parametrlarining `--help` chiqishi va [rasmiy CLI hujjati](https://nextjs.org/docs/app/api-reference/cli/create-next-app) tekshirildi; ichki Git repository yaratilmadi.

| Paket | O‘rnatilgan versiya |
| --- | --- |
| next / eslint-config-next | 16.4.0 |
| react / react-dom | 19.3.0 |
| typescript | 5.9.3 |
| eslint | 9.39.5 |
| @types/node | 20.19.43 |
| @types/react / @types/react-dom | 19.3.0 |

Aniq dependency daraxti `frontend/package-lock.json` da saqlanadi. Yangi checkoutda frontend paketlarini o‘rnatish (Node/npm qayta o‘rnatilmaydi):

```powershell
Set-Location D:\antiplagiat\frontend
npm.cmd ci
```

Ishlab chiqish serveri:

```powershell
Set-Location D:\antiplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

3000-port band bo‘lsa, boshqa bo‘sh portni tanlang. Serverni o‘sha oynada `Ctrl+C` bilan to‘xtating.

Tekshiruvlar va production build:

```powershell
Set-Location D:\antiplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Production builddan keyin bo‘sh lokal portni tanlab ishga tushirish:

```powershell
Set-Location D:\antiplagiat\frontend
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$frontendPort = $listener.LocalEndpoint.Port
$listener.Stop()
Write-Host "Frontend: http://127.0.0.1:$frontendPort"
npm.cmd run start -- --hostname 127.0.0.1 --port $frontendPort
```

Ikkinchi PowerShell oynasida chiqarilgan portni kiriting va HTTP javobini tekshiring:

```powershell
Set-Location D:\antiplagiat\frontend
$frontendPort = Read-Host 'Server oynasidagi port'
$response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$frontendPort/"
$response.StatusCode
$response.Content -match 'Islom akademiyasi — Antiplagiat'
```

Kutiladigan natija: `200` va `True`. Sinov tugagach server oynasida `Ctrl+C` bosing. `node_modules/`, `.next/` va TypeScript build keshi Git’dan chetlashtirilgan.

Oldingi mustaqil reviewda desktop va 375×812 mobil oqim, hisoblash, original koordinatalar, Windows resurs chegaralari va timeout/tozalash tekshirilgan. Yangi auth/tarix bosqichining avtomatik Edge/HTTP dalillari yuqorida. Ilmiy benchmark va murakkab real Word/PDF sifati hali baholanmagan.

Oldingi prototip bosqichida 27 ta haqiqiy HTTP tekshiruvi o‘tgan; yangi bosqich bu regressiyalarni autentifikatsiya va saqlash bilan saqlaydi. Yangi yuklama testi, katta npm audit yoki toza muhitdan o‘rnatish bajarilmadi.

O‘rnatishdagi npm audit ESLint dependency zanjirida 5 ta yuqori darajadagi topilmani ko‘rsatdi (`braces` orqali); avtomatik majburiy downgrade qo‘llanmadi. `npm.cmd audit --omit=dev` esa 0 ta zaiflik ko‘rsatdi. Generator tanlagan ESLint 9.39.5 uchun npm qo‘llab-quvvatlash muddati tugaganligi haqida ogohlantirdi.

## Backendni ishga tushirish va tekshirish

Faqat toza checkoutda, `.venv` hali mavjud bo‘lmasa, Python 3.14 orqali virtual muhit yarating va backend paketlarini o‘rnating. Quyidagi tayyorlash buyruqlarini mavjud `.venv` ustida bajarmang:

```powershell
Set-Location D:\antiplagiat
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Oldingi 14 paketli backend ro‘yxati toza Python 3.14.3 muhitida tekshirilgan. Psycopg qo‘shilgan joriy ro‘yxatni toza muhitdan qayta o‘rnatish hali tekshirilmagan.

PowerShell’da loyiha ildizidan (`D:\antiplagiat`), mavjud `.venv` orqali:

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Ikkinchi PowerShell oynasida haqiqiy HTTP javobini tekshirish:

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -c "import json, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5); body = r.read().decode('utf-8'); print(r.status, body); assert r.status == 200; assert json.loads(body) == {'status': 'ok'}"
```

Kutiladigan natija: `200 {"status":"ok"}`. Serverni ishga tushirgan oynada `Ctrl+C` bilan to‘xtating. `backend/requirements.txt` backend muhiti paketlarining aniq versiyalar bilan qayd etilgan ro‘yxati; paketlarni o‘rnatish vositasi bo‘lgan `pip` bu ro‘yxatga kiritilmagan.

## PostgreSQL readiness

Ilova faqat OS muhit o‘zgaruvchilarini o‘qiydi; `.env` avtomatik yuklanmaydi. `.env.example` faqat namuna va undagi parol bo‘sh. Quyidagi beshta o‘zgaruvchi server ishga tushiriladigan PowerShell jarayonida majburiy:

```powershell
$env:ANTIPLAGIAT_DB_HOST = '127.0.0.1'
$env:ANTIPLAGIAT_DB_PORT = '5432'
$env:ANTIPLAGIAT_DB_NAME = 'antiplagiat'
$env:ANTIPLAGIAT_DB_USER = 'antiplagiat_app'
```

`ANTIPLAGIAT_DB_PASSWORD` ni lokal ravishda shu jarayon muhitiga kiriting; haqiqiy parolni repoga yoki logga yozmang. Standart parol yoki boshqa hisobga avtomatik qaytish yo‘q. Port 1–65535 oralig‘idagi son bo‘lishi kerak. Sozlamalar yo‘q, bo‘sh yoki noto‘g‘ri bo‘lsa, yoxud ulanish/SQL muvaffaqiyatsiz bo‘lsa, `/ready` HTTP 503 va `{"status":"not_ready"}` qaytaradi. `SELECT 1` muvaffaqiyatli bo‘lsa, HTTP 200 va `{"status":"ready"}` qaytaradi. Bu sxema yoki migratsiyalar tayyorligini tekshirmaydi.

Ulanish timeouti 3 soniya, SQL statement timeouti 3000 ms. Har so‘rov o‘z ulanishini ochadi va yopadi. Sinxron endpoint Psycopg chaqiruvlarini FastAPI ishchi threadida bajaradi. Import vaqtida ulanish bo‘lmaydi. Ilova javobida parol, connection string yoki xom drayver xatosi chiqarilmaydi; ilova kodi xom ulanish xatolarini ataylab loglamaydi. Bu uchinchi tomon drayverining barcha loglari tozalanganini kafolatlamaydi; drayver loglarini to‘liq tozalash amalga oshirilmagan.

Server ishlayotganida, loyiha ildizidagi ikkinchi PowerShell oynasida `/ready` ni tekshirish (HTTP 503 ham natija sifatida ko‘rsatiladi):

```powershell
@'
import urllib.request
import urllib.error
try:
    response = urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=10)
except urllib.error.HTTPError as error:
    response = error
with response:
    print(response.status, response.read().decode())
'@ | .\.venv\Scripts\python.exe -
```

Mock testlar va paketlar mosligi:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\.venv\Scripts\python.exe -m pip check
```

Mock tekshiruvlar haqiqiy baza testi emas. Foydalanuvchi Windows’da haqiqiy PostgreSQL bilan `/ready` → HTTP 200 va `{"status":"ready"}` natijasini tasdiqlagan. Psycopg qo‘shilgan joriy requirements ro‘yxati bilan toza muhitdan qayta o‘rnatish hali tekshirilmagan.

## Hali aniqlanmagan ma’lumotlar

Kompyuter xususiyatlari va o‘rnatilgan dasturlar; loyiha joylashuvi; BMI muddati; korpus hajmi va undan foydalanish ruxsati; hosting; tashqi API byudjeti; saqlash muddati va akademiyaning yakuniy rollar siyosati. Bular fakt sifatida taxmin qilinmaydi.
