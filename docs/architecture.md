# Dastlabki arxitektura

Versiya 0.2 · 2026-10-12 · Lokal end-to-end leksik solishtirish prototipi, `GET /health` va PostgreSQL uchun `GET /ready` mavjud. Bu autentifikatsiyasiz prototip; akademiya piloti uchun tayyor tizim emas.

`/health` faqat backend ishlayotganini bildiradi va bazaning tayyorligini tekshirmaydi. `/ready` sinxron Psycopg orqali `SELECT 1` bajaradi: muvaffaqiyatda HTTP 200 va `{"status":"ready"}`, sozlama yoki ulanish/SQL xatosida HTTP 503 va `{"status":"not_ready"}`. Bu sxema tayyorligi tekshiruvi emas. Foydalanuvchi Windows’da haqiqiy PostgreSQL bilan `/ready` → HTTP 200 va `{"status":"ready"}` natijasini tasdiqlagan. Psycopg qo‘shilgan joriy requirements ro‘yxati bilan toza muhitdan qayta o‘rnatish hali tekshirilmagan.

Ulanish uchun `ANTIPLAGIAT_DB_HOST`, `ANTIPLAGIAT_DB_PORT`, `ANTIPLAGIAT_DB_NAME`, `ANTIPLAGIAT_DB_USER`, `ANTIPLAGIAT_DB_PASSWORD` OS muhit o‘zgaruvchilarining barchasi majburiy. Port 1–65535 oralig‘ida tekshiriladi. `.env` avtomatik yuklanmaydi; `.env.example` faqat parolsiz namuna. Standart parol va postgres hisobiga avtomatik qaytish yo‘q.

Import vaqtida ulanish ochilmaydi. Har readiness so‘rovi yangi ulanish ochadi; context manager uni muvaffaqiyat va xatoda yopadi. Ulanish timeouti 3 soniya, SQL statement timeouti 3000 ms. FastAPI sinxron endpointni ishchi threadda bajaradi, event loop bloklanmaydi. Ilova javobida maxfiy sozlamalar yoki xom ulanish xatolari chiqarilmaydi; ilova kodi xom ulanish xatolarini ataylab loglamaydi. Bu uchinchi tomon drayverining barcha loglari tozalanganini kafolatlamaydi; drayver loglarini to‘liq tozalash amalga oshirilmagan. Hozir pool, ORM va migratsiyalar yo‘q.

## 1. Komponentlar

Amaldagi `frontend/` Next.js 16.4.0 (barqaror), React 19.3.0, TypeScript 5.9.3 va ESLint 9.39.5 asosida yaratilgan. `app/layout.tsx` metadata va `lang="uz"` ni, `app/page.tsx` sahifa karkasini beradi. `app/comparison.tsx` fayl tanlash/olib tashlash, kutish, xato, hisobot, manba va parcha tanlash holatlarini boshqaradi. Oddiy CSS desktopda ikki ustun, mobilda bir ustun beradi; tashqi font/CDN yo‘q. Matn React text node orqali render qilinadi; `dangerouslySetInnerHTML` ishlatilmaydi. Login, Tailwind, UI kutubxonasi va React Compiler yo‘q.

Frontend paketlari npm bilan boshqariladi, aniq daraxt `package-lock.json` da saqlanadi. `frontend/` ichida alohida Git repository yo‘q; `node_modules/` va `.next/` Git’dan chetlashtirilgan. Windows PowerShell 5.1 uchun tekshiruvlar:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Ishga tushirish va test buyruqlari [README](../README.md#lokal-hujjat-solishtirish) da berilgan. Muhit: Node.js 24.21.0 va npm 12.0.2. Mustaqil reviewda desktop va 375×812 mobil brauzer oqimi, hisoblash, original koordinatalar, Windows resurs cheklovlari va timeout/tozalash tekshirilgan. Joriy tuzatishlarda brauzer oqimi qayta tekshirilmadi. Avvalgi ESLint audit topilmalari README’da saqlangan, majburiy downgrade yoki yangi katta audit bajarilmadi. Ilmiy benchmark va haqiqiy murakkab Word/PDF hujjatlaridagi sifat hali baholanmagan.

### Amaldagi lokal oqim

1. Brauzer bitta `document` va 1–5 `sources` faylini same-origin `/api/compare` ga yuboradi.
2. Next.js route handler hajm, origin va maxsus headerni tekshiradi; multipart oqimini faqat lokal FastAPI `POST /compare` ga uzatadi. `ANTIPLAGIAT_API_URL` faqat serverda; standart `http://127.0.0.1:8000`. CORS yoki brauzerdagi DB sozlamalari kerak emas.
3. Backend bitta faol so‘rovni qabul qiladi; keyingisiga 429 qaytaradi. `Uploads` fayl va umumiy baytlarni oqim davomida chegaralab, server bergan nomlar bilan tasodifiy vaqtinchalik katalogga yozadi.
4. Alohida worker TXTni UTF-8 sifatida, DOCXni `zipfile` + `defusedxml`, PDFni `pypdf` orqali ajratadi. Makros, tashqi XML entity yoki PDF ichidagi kod bajarilmaydi. Parser stdout/stderr va logging chiqishlari bostiriladi.
5. Original ajratilgan matn va sahifa/paragraf oraliqlari saqlanadi. Normalizatsiyadan keyingi tokenlar originaldagi Unicode code point koordinatalariga bog‘lanadi.
6. Har manba to‘liq ko‘rib chiqiladi. Besh tokenli shingles tengligi ketma-ket teng tokenlar bo‘ylab uzaytiriladi. Original parcha belgima-belgi teng bo‘lsa `exact`, aks holda `shingle`; minimal parcha 5 token. Tinish belgisi, registr, bo‘shliq va apostrof farqi normallashtirilgan moslik sifatida ko‘rinishi mumkin.
7. Umumiy foiz tekshiriluvchi hujjatdagi mos noyob token pozitsiyalari birlashmasidan hisoblanadi. Har manbaning foizi alohida, ularni qo‘shish yo‘q. Hisobot original/manba parchasi, usul, nom, offset, sahifa/paragraf va cheklovlarni beradi.
8. Worker tugagach vaqtinchalik fayllar tozalanadi; HTTP javobi `Cache-Control: no-store`. Natija brauzer xotirasida. Saqlanadigan korpus, DB jadvali yoki qidiruv indeksi yaratilmaydi.

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
| Next.js + TypeScript | Hozir: lokal yuklash va mos parchali hisobot. Reja: autentifikatsiyalangan ish oqimi |
| FastAPI | Hozir: health/readiness va vaqtinchalik hujjat solishtirish. Reja: autentifikatsiya, obyekt ruxsatlari va doimiy ishlar |
| PostgreSQL | Foydalanuvchilar, huquqlar, versiyalar, parchalar, ish holati va FTS indekslari |
| Himoyalangan fayl saqlash | Original hujjatlar va hosila fayllar; dastlab mahalliy yopiq katalog |
| Tahlil modullari | Extraction, normalization, retrieval, matching, reporting |
| Tashqi adapterlar | OpenAlex/Crossref metama’lumoti va alohida ruxsatli matn olish |

Frontendning o‘rnatilgan versiyalari yuqorida va lockfile’da, parserlar requirements’da qayd etilgan; autentifikatsiya kutubxonasi hali tanlanmagan. PostgreSQL fayl saqlashning o‘rniga avtomatik qo‘llanmaydi.

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
