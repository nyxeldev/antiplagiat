# Dastlabki arxitektura

Versiya 0.3 · 2026-10-13 · Lokal autentifikatsiya, shaxsiy hisobot tarixi, leksik solishtirish, `GET /health` va `GET /ready` mavjud. Akademiya piloti uchun tayyor tizim emas.

`/health` faqat backend ishlayotganini bildiradi va bazaning tayyorligini tekshirmaydi. `/ready` sinxron Psycopg orqali `SELECT 1` bajaradi: muvaffaqiyatda HTTP 200 va `{"status":"ready"}`, sozlama yoki ulanish/SQL xatosida HTTP 503 va `{"status":"not_ready"}`. Bu sxema tayyorligi tekshiruvi emas. Foydalanuvchi Windows’da haqiqiy PostgreSQL bilan `/ready` → HTTP 200 va `{"status":"ready"}` natijasini tasdiqlagan. Psycopg qo‘shilgan joriy requirements ro‘yxati bilan toza muhitdan qayta o‘rnatish hali tekshirilmagan.

Ulanish uchun `ANTIPLAGIAT_DB_HOST`, `ANTIPLAGIAT_DB_PORT`, `ANTIPLAGIAT_DB_NAME`, `ANTIPLAGIAT_DB_USER`, `ANTIPLAGIAT_DB_PASSWORD` OS muhit o‘zgaruvchilarining barchasi majburiy. Port 1–65535 oralig‘ida tekshiriladi. `.env` avtomatik yuklanmaydi; `.env.example` faqat parolsiz namuna. Standart parol va postgres hisobiga avtomatik qaytish yo‘q.

Import vaqtida ulanish ochilmaydi. Readiness avvalgi 3 s ulanish va 3000 ms SQL timeout bilan `SELECT 1` bajaradi. Yangi persistence qatlami qisqa psycopg tranzaksiyalari (3 s ulanish, 5 s statement, 3 s lock timeout), commit/rollback va ulanishni yopishdan foydalanadi. Sinxron endpointlar/threadpool DB chaqiruvida event loopni bloklamaydi. Maxfiy qiymat va xom drayver xatolari javob/logga chiqarilmaydi. Pool yoki ORM yo‘q; versiyalangan SQL migratsiya bor.

## 1. Komponentlar

Next.js/React/TypeScript/ESLint versiyalari lockfile’da saqlandi. `account-shell.tsx` login/logout va sessionni, `comparison.tsx` yuklash/saqlashni, `/history` sahifalangan tarixni, `/reports/[id]` snapshotni boshqaradi. `report-view.tsx` yangi/saqlangan hisobot uchun bir xil manba/parcha tanlash va original Unicode highlightni beradi. Backend 401 bo‘lsa maxfiy sahifa unmount qilinadi; focus/pageshow sessionni qayta tekshiradi. CSS desktopda ikki ustun, mobilda bir ustun; tashqi font/CDN va UI kutubxonasi yo‘q. Matn React text node orqali, HTML bajarilmasdan ko‘rsatiladi.

Frontend paketlari npm bilan boshqariladi, aniq daraxt `package-lock.json` da saqlanadi. `frontend/` ichida alohida Git repository yo‘q; `node_modules/` va `.next/` Git’dan chetlashtirilgan. Windows PowerShell 5.1 uchun tekshiruvlar:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Buyruqlar va dalillar [README](../README.md#autentifikatsiya-va-shaxsiy-tarix) da. 39 backend testi, lint/TypeScript/build, disposable PostgreSQL 18 bilan 64 haqiqiy HTTP tekshiruvi va headless Edge 1440×1000/375×812 oqimlari o‘tdi. DB/HTTP va mock dalillar alohida qayd etilgan; production foydalanuvchi DBsiga tegilmadi. Oldingi mustaqil review algoritm/resurs/offsetlarni tekshirgan. Interactive browser helper ishlamadi, screenshot vizual audit bajarilmadi. Avvalgi ESLint audit masalasi saqlandi; benchmark/murakkab real Word/PDF va HTTPS end-to-end hali tekshirilmagan.

### Amaldagi lokal oqim

1. Brauzer bitta `document` va 1–5 `sources` faylini same-origin `/api/compare` ga yuboradi.
2. Next.js route handler hajm, origin va maxsus headerni tekshiradi; multipart oqimini faqat lokal FastAPI `POST /compare` ga uzatadi. `ANTIPLAGIAT_API_URL` faqat serverda; standart `http://127.0.0.1:8000`. CORS yoki brauzerdagi DB sozlamalari kerak emas.
3. Backend bitta faol so‘rovni qabul qiladi; keyingisiga 429 qaytaradi. `Uploads` fayl va umumiy baytlarni oqim davomida chegaralab, server bergan nomlar bilan tasodifiy vaqtinchalik katalogga yozadi.
4. Alohida worker TXTni UTF-8 sifatida, DOCXni `zipfile` + `defusedxml`, PDFni `pypdf` orqali ajratadi. Makros, tashqi XML entity yoki PDF ichidagi kod bajarilmaydi. Parser stdout/stderr va logging chiqishlari bostiriladi.
5. Original ajratilgan matn va sahifa/paragraf oraliqlari saqlanadi. Normalizatsiyadan keyingi tokenlar originaldagi Unicode code point koordinatalariga bog‘lanadi.
6. Har manba to‘liq ko‘rib chiqiladi. Besh tokenli shingles tengligi ketma-ket teng tokenlar bo‘ylab uzaytiriladi. Original parcha belgima-belgi teng bo‘lsa `exact`, aks holda `shingle`; minimal parcha 5 token. Tinish belgisi, registr, bo‘shliq va apostrof farqi normallashtirilgan moslik sifatida ko‘rinishi mumkin.
7. Umumiy foiz tekshiriluvchi hujjatdagi mos noyob token pozitsiyalari birlashmasidan hisoblanadi. Har manbaning foizi alohida, ularni qo‘shish yo‘q. Hisobot original/manba parchasi, usul, nom, offset, sahifa/paragraf va cheklovlarni beradi.
8. Worker tugagach vaqtinchalik fayllar tozalanadi va session qayta tekshiriladi. Hisobot egasiga bog‘langan immutable PostgreSQL snapshot sifatida commit qilinadi; shundan keyin `saved: true`, ID va sana qaytadi. DB xatosi 503, “saqlandi” emas. HTTP javobi `Cache-Control: no-store`. Umumiy korpus/qidiruv indeksi yaratilmaydi.

### Hisoblar va persistence qarori

Mavjud psycopg + parametrli SQL saqlandi: uch jadval va owner predicate uchun ORM zarurati yo‘q. `backend/manage.py` alohida vakolatli hisob va yashirin terminal paroli bilan migratsiyani atomic/advisory lock ostida bajaradi. `schema_migrations` version/checksum orqali qayta ishga tushishni tekshiradi. Mavjud DB o‘chirilmaydi. Runtime superuser yoki DB egasi bo‘lishi rad etiladi; schema USAGE, users SELECT, sessions SELECT/INSERT/DELETE va reports SELECT/INSERT + purge ustunlari UPDATE. UUID sabab sequence grant yo‘q. Runtime migratsiya/akkaunt boshqarmaydi.

`users`: UUID, unique login, Argon2id hash, enabled, role va vaqt. Rol user/reviewer/corpus_manager/admin — kelajak maydoni; hozir hamma faqat o‘z tarixini ko‘radi, admin boshqa hisobotlarga kira olmaydi. Signup/email/reset va rol UI yo‘q. Argon2-cffi va pinned bindings/cffi/pycparser Windows/Python 3.14 da tekshirildi; versiyalar requirements’da.

`sessions`: 32 baytli tasodifiy opaque tokenning SHA-256 hashi, user FK va vaqt/muddat (8 soat). Cookie HttpOnly/Path=/SameSite=Strict; Secure public origin HTTPS bo‘lsa yoqiladi. Token URL/localStoragega berilmaydi; login oldingi cookie sessionini, logout esa amaldagi DB sessionni bekor qiladi. Restart sessionni saqlaydi. Origin/custom header/loopback va Next proxy aniq Host tekshiruvlari CSRFni cheklaydi; CORS ochilmagan. Frontend/backend bir xil `ANTIPLAGIAT_PUBLIC_ORIGIN` bilan sozlanadi; lokal TLS terminatsiyasida backend loopback HTTP bo‘lishi mumkin.

Login generic xato, noma’lum hisob uchun dummy Argon2 verify; 5 daqiqada socket peerga 10 urinish, bir paytda 2 hash. Bu bitta process limiti, restartda yo‘qoladi va proxy foydalanuvchilari loopback limitni bo‘lishadi. Ko‘p worker/ommaviy deployment uchun yetarli deb da’vo qilinmaydi. Cookie/Authorization/parol/matn loglanmaydi. `start_backend.ps1` yashirin parolni process muhitiga beradi va tugaganda avvalgi envni tiklaydi; `.env` ochilmaydi.

`reports`: UUID, owner, created_at, `lexical-shingle-v1`, `uz-latin-v2` va immutable JSONB snapshot. Ajratilgan hujjat/manba matni maxfiy; binarlar doimiy saqlanmaydi. Get/list/delete/retry owner predicate bilan; begona/yo‘q ID 404. Tarix 20 tadan. `(owner, request_key)` unique va input digest ayni yuborishni duplicate qilmaydi; boshqa kontent 409. Frontend kalitni ayni fayl tanlovi uchun xotirada saqlaydi; reloaddan keyin noaniq natijani avval tarixdan tekshirish kerak.

Trigger snapshot tahririni taqiqlaydi. Tasdiqlangan o‘chirish snapshotni NULL qiladi va minimal texnik tombstone qoldiradi; qayta ochish 404, shu kalitni qayta yuborish 410. Bu WAL/backup yoki disk izlarini xavfsiz tozalash kafolati emas. Real pilot uchun DB disk/backuplari va retention siyosati kelishiladi. App administratori privileged DB migratsiya hisobidan alohida tushuncha.

`/compare` uchun loopback host/client va `X-Antiplagiat-Local: 1` talab qilinadi. Ikkala server ham faqat `127.0.0.1` da, backend bitta worker bilan ishlatiladi. Bu lokal cheklovlar autentifikatsiya o‘rnini bosmaydi.

| Resurs | Amaldagi chegara |
| --- | --- |
| Fayllar | 1 tekshiriluvchi + 1–5 manba; 10 MiB/fayl, 30 MiB jami; multipart overhead 64 KiB |
| Matn/token | 200 000 belgi va 30 000 token/fayl; kamida 5 token |
| DOCX | Ochilgan ZIP jami 50 MiB, 1000 element, asosiy XML 8 MiB |
| PDF | 200 sahifa; matnsiz sahifa bo‘lsa butun so‘rov rad etiladi |
| Jarayon | 60 s yuklash; 30 s worker; 512 MiB xotira; Windows Job Object CPU/xotira limiti |
| Solishtirish/hisobot | 300 000 amal/juft, 500 parcha/manba, 12 MiB JSON |

Resurs chegarasini yoqib bo‘lmasa worker ishni boshlamaydi. Timeoutda ota jarayon faqat o‘z workerini to‘xtatib kutadi. Muvaffaqiyat, yuklash/parser xatosi va timeoutda katalog tozalanadi; OS/process majburiy o‘chsa qoldiq fayllar bo‘lishi mumkin. Hech bir limitda jim truncation yoki noto‘g‘ri 0% qaytarilmaydi. Bitta yaroqsiz manba butun so‘rovni xato bilan tugatadi.

API muvaffaqiyatda `status: completed`, qoplash va token hisoblagichlari, original hujjat, manbalar, mosliklar, parametrlar va cheklovlarni qaytaradi. Xatoda `error: {code, message, file}` beriladi: 400 noto‘g‘ri yuklash/son, 413 hajm, 415 kengaytma, 422 parser/matn/solishtirish chegarasi, 429 bandlik; boshqa server xatolari ham matnsiz umumiy xabar beradi. Offsetlar `[start, end)` Unicode code point bo‘yicha; frontend `Array.from(text)` bilan UTF-16 farqini hisobga oladi.

Parser versiyalari va litsenziya dalillari [README](../README.md#lokal-hujjat-solishtirish) va [requirements](../backend/requirements.txt) da. `pypdf` BSD-3-Clause, `defusedxml` PSFL, `python-multipart` Apache-2.0; Python 3.14.3 da o‘rnatish va sintetik format testlari o‘tdi. Mavjud dependencylar yangilanmadi. Toza muhitdan to‘liq qayta o‘rnatish tekshirilmagan.

OCR, iqtibos/bibliografiya filtri, semantik/parafraz aniqlash, internet qidiruvi va akademik sifat benchmarki yo‘q. PDF murakkab maketi va DOCX asosiy qismidan tashqaridagi matnlar cheklov sifatida ko‘rsatiladi. DOCX sahifa raqami taxmin qilinmaydi. O‘xshashlik avtomatik plagiat hukmi emas.

Boshlanishida modulli monolit taklif qilinadi: bitta FastAPI backend ichida mustaqil modullar. Bu kichik jamoada komponentlar orasidagi chegarani saqlab, tarqatilgan xizmatlar xarajatini kamaytiradi.

| Komponent | Vazifasi |
| --- | --- |
| Next.js + TypeScript | Login/logout, lokal yuklash, shaxsiy tarix va snapshot hisoboti |
| FastAPI | Health/readiness, autentifikatsiya/egalik, solishtirish va shaxsiy persistence |
| PostgreSQL | Foydalanuvchilar, huquqlar, versiyalar, parchalar, ish holati va FTS indekslari |
| Himoyalangan fayl saqlash | Original hujjatlar va hosila fayllar; dastlab mahalliy yopiq katalog |
| Tahlil modullari | Extraction, normalization, retrieval, matching, reporting |
| Tashqi adapterlar | OpenAlex/Crossref metama’lumoti va alohida ruxsatli matn olish |

Frontend versiyalari lockfile’da, parser/hash paketlari requirements’da. PostgreSQL hisobot snapshotini saqlaydi; original binar fayl ombori sifatida ishlatilmaydi.

## 2. Tekshiruv oqimi

Quyidagi oqim himoyalangan korpus va tashqi adapterlar uchun kelajak rejasi; amaldagi lokal prototip oqimi yuqorida alohida berilgan.

1. Server foydalanuvchi huquqi va fayl chegaralarini tekshiradi; o‘zgarmas hujjat versiyasi yaratiladi.
2. Matn ajratiladi; original sahifa/paragraf va belgilar koordinatalari saqlanadi.
3. Normalizatsiyalangan matn hamda originalga moslashtirish xaritasi tuziladi.
4. Faqat solishtirishga ruxsat berilgan korpus snapshotidan nomzodlar qidiriladi.
5. Nomzod matnlarda exact/shingle solishtirish va parcha chegaralarini aniqlash bajariladi.
6. Tashqi rejim tasdiqlangan bo‘lsa, siyosat ruxsat bergan so‘rov bilan metama’lumot nomzodlari qidiriladi. Har nomzod uchun huquq va matn mavjudligi alohida tekshiriladi.
7. Takroriy manbalar va qoplangan oraliqlar birlashtiriladi; natija va qamrov saqlanadi.
8. Hisobotni olishda foydalanuvchining joriy huquqi yana tekshiriladi.

Korpusga kiritish tekshiruv uchun yuklashdan alohida amal. Hujjat o‘ziga yoki shu ishning oldingi versiyasiga mos kelishi alohida boshqariladi; yashirin ravishda umumiy foizni oshirmaydi. Qaysi versiyalar chiqarilgani hisobotda yoziladi.

## 3. Algoritmik chegaralar

**Normalizatsiya:** original saqlanadi; Unicode, apostrof, bo‘shliq va registr ishlovi versiyalanadi. Normalizatsiyadan keyingi exact moslik original belgilar darajasidagi aynan tenglikdan farqlanadi. Lotin–kirill transliteratsiyasi keyingi tajriba bo‘lib, original matnni almashtirmaydi. Arab harakatlarini olib tashlash kabi qoidalar alohida baholanadi.

Amaldagi siyosat — `uz-latin-v2`: NFKC + casefold + apostrof folding va faqat U+200B/U+00AD/U+200C/U+FEFF ketma-ketligini bevosita ikki lotin harfi orasida solishtirish nusxasidan chiqarish. Lotin harfi `L*` kategoriyasi va Unicode nomidagi `LATIN` bilan aniqlanadi. Originaldagi indekslar avval aniqlanadi, qolgan normalizatsiyalangan belgilar original guruh oraliqlariga bog‘lanadi; olib tashlangan ichki belgilar highlight oralig‘ida qoladi. Cf/Mn global tozalanmaydi; boshqa yozuvlardagi join-control, matn boshi/oxiri va bo‘shliq/tinish yonidagi belgilar saqlanadi. Versiya `parameters.normalization_version` da, qoida qo‘llangani haqidagi ogohlantirish `limitations` da beriladi va frontendda ko‘rinadi. Original parchalar farqli bo‘lsa `shingle`, teng bo‘lsa `exact`.

ZWSP haqiqiy so‘z chegarasi ham bo‘lishi mumkin; ikki lotin harfi orasidagi shu chegara evristikada birlashtirilishi mumkin. Birikuvchi urg‘u orqali qo‘shnichilik qidirilmaydi. Bu siyosat barcha Unicode chetlab o‘tishlarini hal qilmaydi. Arab harakatlari olib tashlanmaydi: hujjat yoki manbada Unicode nomi `ARABIC` bo‘lgan `M*` belgi topilsa, `limitations` arab harakatlari bo‘yicha tokenizatsiya hali ishonchli emasligini va moslik/umumiy ko‘rsatkich ehtiyotkor talqin qilinishi kerakligini bildiradi. Yangi arab normalizatsiyasi yo‘q; arab tili to‘liq qo‘llanishi da’vo qilinmaydi.

**Retrieval:** PostgreSQL FTS — nomzodlarni saralash vositasi, yakuniy plagiat detektori emas. O‘zbek tili uchun `simple` konfiguratsiyasi boshlang‘ich variant sifatida sinovdan o‘tkaziladi; stemming sifati va morfologik to‘liqlik va’da qilinmaydi. Kichik nazorat korpusida barcha hujjatlar bilan solishtirish FTS topmay qolgan manbalarni o‘lchash uchun etalon bo‘ladi. Shingle indeksi yoki boshqa retrieval yo‘li zaruratga qarab qo‘shiladi.

**Matching:** amaldagi prototip 5 tokenli shingles tuple tengligini tekshiradi, ketma-ket moslikni uzaytiradi va original parchalarni ko‘rsatadi; hash tengligining o‘zi dalil emas. Stop-so‘z va iqtibos filtri yo‘q. Jaccard, boshqa n/threshold va murakkab alignment keyingi nazorat tajribalarida baholanadi; hozirgi parametrlar ilmiy optimal deb tasdiqlanmagan.

**Keyingi tajribalar:** MinHash/LSH — nomzod qidirishni tezlatish; TF-IDF + cosine — leksik baseline; Sentence Transformers — ma’no yaqinligi nomzodlari. pgvector embedding qidiruvi uchun. Semantik yaqinlik parafrazning avtomatik isboti emas. Model litsenziyasi, til sifati, xotira talabi va lokal ishlashi tanlashdan oldin tekshiriladi.

## 4. Minimal mantiqiy ma’lumotlar modeli

| Entitet | Asosiy ma’lumot |
| --- | --- |
| User / Role / Assignment | Hisob, rol, tekshiruvga biriktirish |
| Document / DocumentVersion | Egasi, tur, immutable versiya, hash, fayl joyi, matn holati |
| CorpusEntry / Permission | Qaysi versiya, ruxsat dalili, solishtirish va ko‘rsatish huquqi |
| Chunk | Original koordinata, normalizatsiya xaritasi, matn, token oralig‘i |
| CheckJob | Hujjat versiyasi, snapshot, sozlamalar, holat, progress, xato |
| SourceRecord / SourceVersion | DOI yoki boshqa ID, provider, versiya, URL, kontent hash va litsenziya |
| RetrievalAttempt | Provider, vaqt, qidiruv rejimi, natija/xato, limit holati |
| Match | Hujjat/manba oraliqlari, usul, ball, dalil darajasi |
| Report / AuditEvent | Hisobot versiyasi, hisoblash sozlamalari va ruxsatli audit |

Litsenziya va huquq asl manba nusxasiga bog‘lanadi. Bir DOI ostidagi preprint va nashr versiyasi bir xil matn deb olinmaydi. Embedding ham maxfiy hosila ma’lumot hisoblanadi.

## 5. Tashqi manbalar: dastlabki tekshiruv

Rasmiy hujjatlar 2026-10-12 kuni o‘qildi. Jonli integratsiya, API kaliti, tarif limiti va aniq maqola litsenziyasi hali sinovdan o‘tkazilmagan.

| Manba | Tasdiqlangan imkoniyat | Loyihadagi qoida |
| --- | --- | --- |
| OpenAlex | Ilmiy ishlar metama’lumoti va nusxa joylashuvlari; `landing_page_url`, `pdf_url`, `is_oa`, `license`, `version` maydonlari. Ayrim ishlar uchun keshlangan kontent alohida ko‘rsatiladi [S1–S2] | PDF havolasi yoki OA belgisi matnni qayta ishlash/saqlashga barcha huquqlar berilganini anglatmaydi; nusxa va foydalanish sharti tekshiriladi |
| Crossref | DOI va bibliografik metama’lumot, mavjud bo‘lsa annotatsiya/litsenziya; API ro‘yxatdan o‘tmasdan ochiq. Ayrim annotatsiyalar mualliflik huquqiga ega bo‘lishi mumkin [S3] | Annotatsiya uchun ham huquqni hisobga olish; DOI yozuvini to‘liq maqola deb qabul qilmaslik |
| Crossref full-text links | Crossref metama’lumotdagi havolalar orqali tashqi matnni topishga yordam beradi; havola kirishni kafolatlamaydi, host obuna/login/TDM sharti qo‘yishi mumkin [S4] | Matn tegishli hostdan faqat ruxsatli tartibda olinadi; yopiq kirish chetlab o‘tilmaydi |

Har adapter joriy autentifikatsiya, tarif/byudjet, tezlik chegarasi, foydalanish sharti, kesh/saqlash/qayta tarqatish ruxsati va to‘liq matn olish yo‘lini ulashdan oldin qayd qiladi. Belgilangan byudjetdan tashqari xarajat yoki pullik obuna avtomatik yoqilmaydi. Narxlar bu hujjatda qotirib qo‘yilmagan.

Kontent dalili va olish holati alohida maydonlar:

- `content_level`: metadata, abstract, full_text.
- `access_state`: not_attempted, permitted, restricted, unknown.
- `fetch_state`: not_attempted, fetched, unavailable, failed.
- `analysis_state`: not_run, analyzed, partial, extraction_failed.

`full_text` bilan solishtirildi degan xulosa uchun huquq tasdiqlangan, matn olingan va extraction/tahlil yetarli bo‘lishi shart. URL alohida maydon; uning mavjudligi dalil darajasini oshirmaydi. Tashqi xizmat ishlamasa ichki natija saqlanadi, umumiy ish `partial` bo‘lishi mumkin.

## 6. Ishlar navbati va kengayish

Kichik algoritmik prototip nazorat namunalarida sinxron ishlashi mumkin. Real ko‘p foydalanuvchili pilotda uzoq ishlar uchun durable job yozuvi, uzilishdan tiklanish, idempotent qayta urinish va parallel ish limiti talab qilinadi. Faqat jarayon xotirasidagi fon vazifasiga tayanilmaydi. Shu ehtiyoj paydo bo‘lganda Redis/Celery yoki muqobil worker yechimi asoslab tanlanadi. OpenSearch faqat FTS tezligi/qamrovi o‘lchovlari ehtiyojni ko‘rsatsa qo‘shiladi.

## 7. Qarorlar qaydi

Modulli monolit, ichki korpusdan boshlash va tashqi tarmoqni standart holatda o‘chirish — ushbu versiyadagi takliflar. Katta o‘zgarish oldidan sabab, muqobillar, foyda, migratsiya va tekshiruv rejasi yoziladi.

## Manbalar

- [S1: OpenAlex API](https://help.openalex.org/api/)
- [S2: OpenAlex Locations](https://help.openalex.org/data/locations/)
- [S3: Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [S4: Crossref — Accessing full texts](https://www.crossref.org/documentation/retrieve-metadata/text-and-data-mining/)
