# Ish rejasi va BMI tajribalari

Versiya 0.5 · 2026-10-14.

**Bu bosqichda bajarildi — ichki ilmiy korpus MVP, real bazaga qo‘llangan.** Ruxsat asosi majburiy bo‘lgan ichki korpus (`corpus_documents`/`corpus_chunks`, migratsiya `002_internal_corpus`), PostgreSQL FTS (`simple`) bilan nomzod tanlash (`pg-fts-candidate-v1`), nomzodlarni **mavjud** exact/5-token shingle algoritmi bilan solishtirish va natijani mavjud hisobot snapshotiga qo‘shish. Korpus tekshiruvi opt-in, default o‘chiq; qo‘lda 1–5 manba oqimi o‘zgarmagan.

Migratsiya `antiplagiat` ishlab chiqish bazasiga **haqiqatan qo‘llandi** (avval to‘liq `pg_dump` zaxirasi olingach): `D:\antiplagiat_backups\antiplagiat-pre-002-20261014-135628.dump` (40 345 bayt). `migrate --check` toza o‘tdi, so‘ng `migrate` ikkala migratsiyani (`001_accounts_reports`, `002_internal_corpus`) ro‘yxatga oldi; `corpus_documents`/`corpus_chunks` jadvallari mavjudligi tasdiqlandi.

**Korpus boshqaruv rol matritsasi** (koddagidek, `backend/auth.py` dagi `CORPUS_MANAGEMENT_ROLES`):

| Rol | `/corpus/documents*` | Shaxsiy hisobotlar |
| --- | --- | --- |
| `admin` | 200 | faqat o‘ziniki |
| `corpus_manager` | 200 | faqat o‘ziniki |
| `user` | 403 | faqat o‘ziniki |
| `reviewer` | 403 | faqat o‘ziniki |
| login yo‘q | 401 | 401 |

`corpus_manager` boshqa hech qanday qo‘shimcha huquqqa ega emas — faqat korpus boshqaruvi uchun. `admin`/`corpus_manager` ham boshqa foydalanuvchining shaxsiy hisobotini ko‘rmaydi.

**Shu bosqichda topilgan va tuzatilgan nuqson:** qisqa korpus hujjatlarida kontekst oynasi (`CORPUS_CONTEXT_CHARS = 200`, flat) hujjatning butun qolgan matnini fosh qilishi mumkin edi — bu `docs/requirements.md` 2.1-bo‘limidagi «to‘liq matnni hech qachon olmaydi» talabini buzgan haqiqiy nuqson edi (mexanizm xato ishlagani emas, kafolat qisqa hujjatlar uchun yetarli bo‘lmagani). `CORPUS_CONTEXT_FRACTION = 0.5` bilan tuzatildi — tafsilot va test nomi [docs/architecture.md](architecture.md), 1-bo‘lim, «Qisqa korpus hujjatlarida kontekst sizishi» da.

**Keyingi qadamlar:** retrieval sifatini ruxsatli nazorat korpusida o‘lchash (recall/precision, morfologik variantlar `simple` konfiguratsiyasida bog‘lanmaydi — benchmark hujjatlari korpusdan **qisman** o‘xshash, mos kelmaydigan dum bilan tanlanishi shart, [architecture.md](architecture.md) da izohlangan); korpus uchun admin UI sahifasi (hozir faqat CLI/HTTP); retention/backup siyosati; `scripts/check_e2e.py` hali korpusni qamramaydi (faqat qo‘lda browser tekshiruvi bo‘ldi); DOCX/PDF formatidagi korpus kiritish yo‘li (`corpus-add`) faqat TXT bilan sinaldi; so‘ng kengroq indekslash. OCR, tashqi qidiruv, parafraz va semantik model hamon doiradan tashqarida.

**Ma’lum cheklov — ko‘p so‘rov bo‘yicha excerpt jamlanishi:** korpus excerpt kafolati (`CORPUS_CONTEXT_CHARS`/`CORPUS_CONTEXT_FRACTION`/`CORPUS_EXCERPT_BUDGET`) faqat bitta hisobot doirasida hisoblanadi; ko‘p marta turlicha qisman mos matn yuborib, natijalarni tashqarida birlashtirishdan himoya yo‘q ([architecture.md](architecture.md) da tafsilot). Kelajak yechimlari: (1) foydalanuvchi×korpus hujjati darajasida kümülatif excerpt hisobi (DB’da saqlanadigan, so‘rovlar oralig‘ida budjetni kamaytiruvchi hisoblagich), (2) korpus excerpt chiqarilishining audit jurnali (kim, qachon, qaysi hujjatdan, qancha belgi ko‘rdi), (3) `/compare?include_corpus=true` uchun alohida so‘rov tezligi cheklovi. Kod hozircha o‘zgartirilmagan.

**Test avtomatlashtirishdagi ma’lum bo‘shliq:** o‘chirish oqimidagi native `window.confirm` oynasini ichki brauzer vositasi qabul qila olmaydi — oyna ochiladi, lekin faqat bekor qilinadi va `DELETE` so‘rovi yuborilmaydi. Bu ilovaning to‘g‘ri xulqi (o‘chirish haqiqatan tasdiqlash ortida), ammo uchdan-uchiga avtomatik regressiyani to‘sadi. Variantlar keyin baholanadi: `window.confirm` o‘rniga ilova ichidagi modal dialog, yoki dialogni qabul qila oladigan test drayveri (masalan Playwright/CDP). Hozircha bu qadam qo‘lda tasdiqlanadi.

Bu kelajakdagi yo‘l xaritasi. Jadvaldagi barcha vazifalar hozir bajarish uchun topshiriq emas. Prototipga autentifikatsiya va shaxsiy tarix qo‘shildi (3–6-bosqichlarning ayrim qismlari). Doimiy korpus, FTS, topshiriq/rol bo‘yicha ruxsatlar va akademik baholash hali bajarilmagan. Keyingi vazifa alohida kelishiladi.

Amaldagi natija: CLI akkaunti bilan login/logout, himoyalangan TXT/DOCX/matnli PDF solishtirish, original koordinatalar, exact/5-token shingle va PostgreSQL’dagi shaxsiy snapshot. Users/sessions/reports migratsiyasi, scoped sahifalangan tarix, qayta ochish va tasdiqlangan o‘chirish bor. Fayllar vaqtinchalik, snapshot matni maxfiy. Admin boshqa hisoblar hujjatlarini ko‘rmaydi. Bu akademiyada ishlatishga tayyor tizim yoki to‘liq MVP-1 emas.

Oldingi mustaqil review algoritm, offset, Windows resurslari va desktop/mobil oqimini tekshirgan. Yangi auth/tarix bosqichi: 39 backend testi, frontend lint/TypeScript/build, disposable PostgreSQL bilan 64 haqiqiy HTTP tekshiruvi va Edge 1440×1000/375×812 avtomatik oqimi. Keyingi ishlar: ilmiy benchmark va murakkab real Word/PDF sifati, topshiriq/rol ruxsatlari va pilot siyosati, so‘ng korpus/indekslash. OCR/tashqi qidiruv/parafraz/semantik model yo‘q.

Review tuzatishi: normalizatsiya siyosati `uz-latin-v2` NFKC/casefold/apostrof ishloviga qo‘shimcha U+200B/U+00AD/U+200C/U+FEFF ketma-ketligini faqat bevosita lotin harflari orasida solishtirish nusxasidan chiqaradi. Original matn, highlight offsetlari va exact/normalizatsiyalangan yorliqlar saqlanadi; versiya hisobot metama’lumotida, ogohlantirish frontendda ko‘rinadi. Barcha Cf/Mn yoki boshqa yozuvlardagi join-control belgilarini global o‘chirish yo‘q. ZWSP haqiqiy so‘z chegarasi bo‘lishi mumkin, shu sabab evristika barcha Unicode chetlab o‘tishlarini hal qilmaydi. Arab harakatlari bo‘yicha tokenizatsiya ochiq kamchilik: harakatlar yashirin olib tashlanmaydi; aniqlanganda moslik va umumiy ko‘rsatkichni ehtiyotkor talqin qilish ogohlantirishi beriladi. Arab tilini to‘liq qo‘llash va yangi arab normalizatsiyasi bu bosqichga kirmaydi.

## 1. Bosqichlar va o‘tish shartlari

| Bosqich | Natija | Keyingisiga o‘tish sharti | Taklif etiladigan commit |
| --- | --- | --- | --- |
| 0 | To‘rtta boshlang‘ich hujjat | Fayllar ochiladi, chegaralar ko‘rib chiqiladi | `docs: define initial scope and architecture` |
| 1 | Windows muhiti va tanlangan papka inventari | PowerShell, Git, Python, Node va PostgreSQL holati qayd etiladi; hech narsa ko‘r-ko‘rona o‘rnatilmaydi | `docs: record development environment` |
| 2 | Minimal repo, backend/frontend va DB ulanishi | Health-check, sahifa ochilishi va DB ulanish testi o‘tadi; maxfiy fayllar Gitdan chiqariladi | `chore: initialize application skeleton` |
| 3 | Ruxsatli sinov korpusi va extraction | TXT, so‘ng DOCX/PDF nazorat misollari; bo‘sh/buzilgan/skan fayl natijasi to‘g‘ri | `feat: extract and normalize document text` |
| 4 | Exact baseline | Kiritilgan nazorat mosliklari va original koordinatalari tekshiriladi | `feat: add exact matching baseline` |
| 5 | FTS va shingle matching | Retrieval recall etalon bilan o‘lchanadi; parcha va qoplash testi o‘tadi | `feat: retrieve and compare lexical matches` |
| 6 | Rollar, himoyalangan yuklash va hisobot — MVP-1 | Talablar hujjatidagi ruxsat/foiz/qamrov testlari o‘tadi; haqiqiy hujjatlar faqat shu himoyadan keyin | `feat: deliver protected internal reports` |
| 7 | Tashqi providerlar metama’lumoti | OpenAlex va Crossref alohida: shartlar, kalit/limit, null maydonlar, timeout/429 testlari | `feat: discover external source candidates` |
| 8 | Ruxsatli to‘liq matn — MVP-2 | Haqiqatan olingan matn dalili; restricted, unavailable va partial holatlar; tashqi maxfiylik siyosati | `feat: compare permitted external full text` |
| 9 | Tezkor va semantik tajribalar | MinHash/LSH, TF-IDF va embedding variantlari bir xil benchmarkda baholanadi | `research: compare retrieval and similarity methods` |
| 10 | Yozuv/til tajribalari | Har til va lotin–kirill rejimi bo‘yicha alohida metrikalar | `research: evaluate multilingual normalization` |
| 11 | BMI natijalari va cheklangan pilot | Takrorlanuvchi tajriba, backup/restore, kirish va yuklama tekshiruvi, tasdiqlangan ma’lumot siyosati | `docs: report experiments and pilot limits` |

Commitlar faqat tegishli ish tekshirilib bo‘lgach va joriy topshiriq ruxsati bilan yaratiladi. Zarur bo‘lsa bosqich ichida kichik mantiqiy commitlarga ajratiladi; avvalgi begona ishchi o‘zgarishlar aralashtirilmaydi. Amaldagi commitlar uchun Git tarixiga qarang.

## 2. Ilmiy savollar

- Exact va shingle usullari nazoratli ko‘chirish/ozroq tahrirda qanday natija beradi?
- FTS yoki MinHash/LSH qidiruvni tezlatganda qancha haqiqiy manbani topmay qoladi?
- TF-IDF va semantik model parafrazga o‘xshash holatlarda recallni oshiradimi, noto‘g‘ri musbatlarni ko‘paytiradimi?
- O‘zbek apostroflari va keyinchalik lotin–kirill normalizatsiyasi aniqlikka qanday ta’sir qiladi?
- Iqtiboslar, diniy manbalardagi umumiy parchalar va standart akademik matnlar natijani qanday o‘zgartiradi?

Ilmiy yangilik hozircha isbotlangan emas. Adabiyotlar tahlili, baseline taqqoslashlari va tajriba natijalari asosida qanday hissa borligi aniqlanadi.

## 3. Test to‘plami

Dastlab sun’iy yoki aniq ruxsatli matnlardan smoke-test; u ilmiy sifat da’vosi uchun yetarli emas. Asosiy to‘plam hajmi korpus va annotatsiya resurslari ma’lum bo‘lgach belgilanadi.

To‘plamga so‘zma-so‘z ko‘chirish, mayda tahrir, inson tayyorlagan parafraz, to‘g‘ri iqtibos, umumiy ibora va mavzusi o‘xshash lekin ko‘chirilmagan qiyin salbiy misollar kiritiladi. Har misolda manba, aniq original oraliqlar, til, o‘zgarish turi, ruxsat va belgilovchi ma’lumoti bo‘ladi. Sintetik va tabiiy misollar alohida hisobot qilinadi.

Manba hujjat oilalari bo‘yicha train/dev/test ajratiladi. Bir maqolaning nusxalari, tarjimalari, parafrazlari va hosila parchalarini turli splitlarga tarqatib ma’lumot sizishiga yo‘l qo‘yilmaydi. Testdagi ma’lum manbalar qidiruv indeksida bo‘lishi mumkin; ularning belgilari va hosila misollari threshold/model sozlashga ishlatilmaydi. Supervised o‘qitish bo‘lmasa ham dev/test ajratilishi saqlanadi.

Kamida tanlangan qism ikki baholovchi tomonidan belgilanib, kelishmovchiliklar muhokama qilinishi rejalashtiriladi. Akademik plagiat hukmi bilan matniy o‘xshashlik yorlig‘i birlashtirilmaydi.

## 4. Baholash protokoli

| Ko‘rsatkich | Oldindan belgilangan hisoblash |
| --- | --- |
| Precision | `TP / (TP + FP)`; asosiy birlik — belgilangan hujjat–manba parcha jufti |
| Recall | `TP / (TP + FN)` shu birlikda |
| F1 | `2PR / (P + R)` |
| Noto‘g‘ri musbatlar | FP soni va `FP / (FP + TN)`; salbiy juftlar to‘plami oldindan muzlatiladi |
| Retrieval recall@k | Qaytarilgan top-k ichidagi haqiqiy manbalar / mavjud haqiqiy manbalar |
| Parcha aniqligi | Hujjat va manba token oraliqlari bo‘yicha precision/recall/F1; baholash qoidasi oldindan qayd etiladi |
| Vaqt | Extraction, retrieval, matching va umumiy vaqt; takroriy yugurishlarda median va p95 |
| Qamrov | Korpus hujjatlari, topilgan nomzodlar, amalda olingan/tahlil qilingan to‘liq matnlar va xatolar soni |

Parcha jufti threshold orqali tasniflanadi; threshold devda tanlanadi va testda o‘zgarmaydi. Bo‘sh maxrajlar `N/A` va hisoblagichlar bilan ko‘rsatiladi. Parcha chegaralari uchun alignment/overlap qoidasi testdan oldin belgilanadi. Hujjat darajasidagi natijalar qo‘shimcha bo‘lishi mumkin, parcha metrikalari bilan aralashtirilmaydi.

Tashqi qamrov «internetning X foizi» deb hisoblanmaydi. Maxraji ma’lum nazorat manbalari bilan coverage yoki amalda tekshirilgan manbalar soni beriladi. Annotatsiya va metama’lumot sonlari to‘liq matnlar sonidan ajratiladi.

## 5. Adolatli taqqoslash

1. Bir xil test hujjatlari, korpus snapshoti va preprocessing variantlari qayd etiladi.
2. Matching algoritmlari bir xil tayyor nomzodlar ustida; retrieval variantlari esa recall@k va vaqt bo‘yicha alohida taqqoslanadi. So‘ng butun pipeline baholanadi.
3. TF-IDF lug‘ati/IDF, model va thresholdlar test yorliqlaridan foydalanmasdan belgilanadi; fit qilingan korpus aniq qayd etiladi.
4. Algoritmlar bosqichma-bosqich qo‘shilib, har qo‘shimchaning ta’siri alohida o‘lchanadi.
5. Versiyalar, parametrlar, seed, apparat, kesh holati, korpus hash va vaqt logi saqlanadi.
6. Tashqi API o‘zgaruvchanligi uchun ruxsat etilgan javob/nusxa snapshotlari ishlatiladi; jonli tarmoq va lokal algoritm vaqtini alohida berish rejalashtiriladi.
7. Faqat yaxshi chiqqan misollar tanlab olinmaydi; xato turlari, cheklovlar va to‘plam hajmi hisobotda ochiq beriladi.

## 6. Hozirgi qadamni tekshirish

- Backend unittestlari exact/farqli/qisman/takroriy moslik, Unicode/apostrof, original offsetlar, formatlar, xatolar, hajm/arxiv/resurs chegaralari va vaqtinchalik fayllar tozalanishini tekshiradi. Readiness regressiya testlari ham bajariladi.
- Frontend ESLint, TypeScript va production build tekshiriladi.
- `scripts/check_e2e.py` sun’iy namunalar bilan production frontend → FastAPI → worker → hisobot yo‘lini haqiqiy HTTP orqali tekshiradi; bo‘sh loopback portlari va faqat o‘zi yaratgan jarayonlardan foydalanadi.
- Haqiqiy PostgreSQL/HTTP testi alohida disposable instansiyada: privileged migration va cheklangan runtime hisoblari, ikki sun’iy app foydalanuvchisi, session muddati/logout/restart, egalik, saqlash/tarix/ochish/o‘chirish, retry, DB saqlash xatosi va cleanup. Mavjud foydalanuvchi bazasida migratsiya yoki sinov bajarilmaydi; SQLite/mock PostgreSQL testi sifatida ko‘rsatilmaydi.
- Yangi auth/tarix browser regressioni headless Edge’da desktop 1440×1000 va mobil 375×812: login, upload/retry, snapshot highlight/warnings, history, owner denial, cancel/delete, logout. Bu avtomatik UI oqimi; screenshot vizual auditi emas. HTTPS to‘liq oqimi va mavjud foydalanuvchi DBsida migratsiya tekshirilmagan.
- Npm auditning avvalgi ESLint dependency muammosi README’da saqlangan; bu vazifada majburiy downgrade yoki katta takroriy audit bajarilmadi.

- Ichki korpus bosqichi uchun: `backend/tests/test_corpus.py` (chunking/offset mosligi, so‘rov oynalari, metama’lumot qoidalari, excerpt kesish va budjet, rol tekshiruvi) va `backend/tests/test_corpus_integration.py` (haqiqiy disposable PostgreSQL: chunk+FTS indeksi, takror `content_sha256` rad etilishi, withdraw matnni o‘chirishi, retrieval ijobiy/salbiy holati, `include_corpus` o‘chiq/yoniq, non-admin javobida to‘liq korpus matni yo‘qligi, shaxsiy hisobot matni korpusga tushmasligi, runtime hisobining DELETE/provenance urinishlari bloklanishi). Mavjud testlar o‘zgartirilmagan yoki yumshatilmagan.

Amalda bajarilgan tekshiruv natijalari va PowerShell buyruqlari [README](../README.md#lokal-hujjat-solishtirish) da. Yuklama, haqiqiy ilmiy korpus va akademik sifat tekshiruvlari hali bajarilmagan.
