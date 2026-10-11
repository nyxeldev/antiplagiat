# Dastlabki arxitektura

Versiya 0.1 · 2026-10-12 · Minimal FastAPI backend va `GET /health` mavjud; qolgan arxitektura rejalashtirilgan.

`/health` faqat backend ishlayotganini bildiradi va bazaning tayyorligini tekshirmaydi. PostgreSQL ulanishi qo‘lda tekshirilgan, ammo backend hali ma’lumotlar bazasiga integratsiya qilinmagan.

## 1. Komponentlar

Boshlanishida modulli monolit taklif qilinadi: bitta FastAPI backend ichida mustaqil modullar. Bu kichik jamoada komponentlar orasidagi chegarani saqlab, tarqatilgan xizmatlar xarajatini kamaytiradi.

| Komponent | Vazifasi |
| --- | --- |
| Next.js + TypeScript | Yuklash, tekshiruv holati, mos parchalar va hisobot interfeysi |
| FastAPI | Autentifikatsiya integratsiyasi, ruxsatlar, hujjatlar, tekshiruv va hisobot API |
| PostgreSQL | Foydalanuvchilar, huquqlar, versiyalar, parchalar, ish holati va FTS indekslari |
| Himoyalangan fayl saqlash | Original hujjatlar va hosila fayllar; dastlab mahalliy yopiq katalog |
| Tahlil modullari | Extraction, normalization, retrieval, matching, reporting |
| Tashqi adapterlar | OpenAlex/Crossref metama’lumoti va alohida ruxsatli matn olish |

Texnologiya versiyalari, autentifikatsiya kutubxonasi va parserlar Windows muhiti tekshirilgach tanlanadi. PostgreSQL fayl saqlashning o‘rniga avtomatik qo‘llanmaydi.

## 2. Tekshiruv oqimi

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

**Retrieval:** PostgreSQL FTS — nomzodlarni saralash vositasi, yakuniy plagiat detektori emas. O‘zbek tili uchun `simple` konfiguratsiyasi boshlang‘ich variant sifatida sinovdan o‘tkaziladi; stemming sifati va morfologik to‘liqlik va’da qilinmaydi. Kichik nazorat korpusida barcha hujjatlar bilan solishtirish FTS topmay qolgan manbalarni o‘lchash uchun etalon bo‘ladi. Shingle indeksi yoki boshqa retrieval yo‘li zaruratga qarab qo‘shiladi.

**Matching:** exact moslikdan keyin token n-gram/shingle Jaccard balli va real parcha alignmenti. Hash tengligi yakuniy dalil emas, matn bilan tekshiriladi. n, minimal mos parcha uzunligi, stop-so‘zlar va threshold validatsiyada tanlanadi.

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
