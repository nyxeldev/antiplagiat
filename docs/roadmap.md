# Ish rejasi va BMI tajribalari

Versiya 0.2 · 2026-10-12.

Bu kelajakdagi yo‘l xaritasi. Jadvaldagi barcha vazifalar hozir bajarish uchun topshiriq emas. Boshlang‘ich hujjatlar va ilova karkasi mavjud; 3–5-bosqichlarning ayrim qismlarini qamrab oluvchi lokal end-to-end prototip yaratildi. Doimiy korpus, FTS, autentifikatsiya va akademik baholash hali bajarilmagan. Keyingi vazifa alohida kelishiladi. Muddatlar hali belgilanmagan.

Amaldagi natija: bitta hujjat va 1–5 manbani TXT/DOCX/matnli PDF formatida yuklash, original koordinatalarni saqlash, exact/5-token shingle solishtirish, noyob tokenlar qoplash foizi va manba/parcha tanlanadigan hisobot. Fayllar vaqtinchalik; DB jadvallari yaratilmagan. Bu akademiyada ishlatishga tayyor tizim yoki himoyalangan MVP-1 emas.

Mustaqil reviewda desktop va 375×812 mobil brauzer oqimi, hisoblash, original koordinatalar, Windows resurs cheklovlari hamda timeout/tozalash tekshirilgan. Keyingi rejalashtiriladigan ishlar: ruxsatli ilmiy benchmark va haqiqiy murakkab Word/PDF hujjatlarida extraction/matching sifatini baholash, autentifikatsiya va obyekt ruxsatlari, so‘ng korpus/indekslash. Benchmark va murakkab haqiqiy hujjatlar hali baholanmagan. OCR, tashqi qidiruv, parafraz va semantik model bu prototipga kiritilmagan.

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
- Haqiqiy PostgreSQL readiness muvaffaqiyati oldin foydalanuvchi tomonidan tasdiqlangan. Ushbu solishtirish testlari DBdan mustaqil; yangi haqiqiy DB sinovi bajarilmadi.
- Mustaqil reviewda desktop va 375×812 mobil brauzer oqimi tekshirilgan; joriy tuzatishlarda bu vizual tekshiruv qayta bajarilmadi.
- Npm auditning avvalgi ESLint dependency muammosi README’da saqlangan; bu vazifada majburiy downgrade yoki katta takroriy audit bajarilmadi.

Amalda bajarilgan tekshiruv natijalari va PowerShell buyruqlari [README](../README.md#lokal-hujjat-solishtirish) da. Yuklama, haqiqiy ilmiy korpus va akademik sifat tekshiruvlari hali bajarilmagan.
