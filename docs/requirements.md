# Talablar

Versiya 0.1 · 2026-10-12 · Boshlang‘ich taklif.

## 1. Bosqichlar doirasi

**MVP-1:** ichki ruxsatli korpus, matn ajratish, exact va shingle asosidagi mosliklar, himoyalangan hisobot. Dastlab o‘zbek lotin yozuvidagi matnlar bilan baholanadi. TXT, DOCX va matn qatlamli PDF qo‘llab-quvvatlash maqsad qilinadi; ular ketma-ket qo‘shiladi. Skan PDF uchun OCR hali qo‘llanmaydi.

**MVP-2:** OpenAlex va Crossref orqali manba nomzodlari; foydalanish shartlari tekshirilgan ochiq to‘liq matnlar bilan solishtirish. Faqat ichki tekshiruv mavjud paytda mahsulot «internetdan tekshiradi» deb taqdim etilmaydi.

**Tadqiqot bosqichi:** TF-IDF, tezkor nomzod qidiruv va semantik tahlilni taqqoslash. O‘zbek kirill, rus, ingliz va arab tillari hamda yozuvlararo solishtirish uchun alohida testlar. Barcha tillarda bir xil sifat kafolatlanmaydi.

## 2. Rollar va kirish

| Rol | Dastlabki huquqlar |
| --- | --- |
| Muallif/talaba | O‘z hujjatini yuklash, o‘z tekshiruvi va hisobotini ko‘rish |
| Tekshiruvchi | Faqat o‘ziga biriktirilgan hujjatlarni tekshirish va ko‘rish |
| Korpus mas’uli | Ruxsat dalili bilan korpusga hujjat kiritish yoki chiqarish |
| Administrator | Hisoblar, rollar va tizim sozlamalarini boshqarish |

Administrator roli avtomatik ravishda barcha ilmiy matnlarni o‘qish huquqini bermaydi. Solishtirishga ruxsat va manba matnini foydalanuvchiga ko‘rsatish huquqi alohida belgilanadi. Cheklangan manba uchun faqat ruxsat etilgan rekvizit yoki parcha ko‘rsatiladi. Barcha ruxsatlar serverda tekshiriladi; interfeysdagi yashirish yetarli emas.

## 3. Funksional talablar va tekshirish mezonlari

| ID | Talab | Qabul mezoni |
| --- | --- | --- |
| F01 | Faylni tekshirish | Ruxsat etilmagan tur, buzilgan fayl va belgilangan hajm chegarasidan oshish tushunarli xato beradi |
| F02 | Matn ajratish | Nazorat hujjatidagi matn va parcha joylari tiklanadi; bo‘sh/skan fayl «0%» bilan muvaffaqiyatli deb chiqmaydi |
| F03 | Normalizatsiya | Unicode, bo‘shliqlar va apostrof variantlari bir xil qoida bilan ishlanadi; originalga qaytish xaritasi saqlanadi |
| F04 | Ichki korpus | Faqat tasdiqlangan hujjat versiyalari indekslanadi; oddiy yuklash hujjatni avtomatik umumiy korpusga qo‘shmaydi |
| F05 | Exact matching | Nazoratdagi aynan ko‘chirilgan parcha va uning manbasi topiladi |
| F06 | Shingle mosligi | Belgilangan n va threshold bilan nazorat misollari tekshiriladi; topilgan parcha original bilan tekshiriladi |
| F07 | Hisobot | Hujjat/manba parchalari, joylari, usul, ko‘rsatkich, qamrov va xatolar ko‘rinadi |
| F08 | Ish holati | queued, running, completed, partial yoki failed; tashqi xizmat xatosi «manba yo‘q» deb yashirilmaydi |
| F09 | Tashqi qidiruv | Metama’lumot/annotatsiya/havola/to‘liq matn turini aniq ajratadi |
| F10 | To‘liq matnni olish | Huquq, olish natijasi va ajratish sifati tekshirilmasdan full-text tekshiruvi deb belgilanmaydi |
| F11 | Cheklash va o‘chirish | Korpusdan chiqarilgan manba yangi tekshiruvlarda ishlatilmaydi; indeks, kesh, hosila matn va zaxiralardagi hayot sikli hujjatlashtiriladi |
| F12 | Takrorlanuvchanlik | Hisobotda hujjat/korpus versiyasi, algoritm, parametrlar, vaqt va normalizatsiya versiyasi qayd qilinadi |

PDF uchun mavjud sahifa raqami, DOCX/TXT uchun paragraf va matn oralig‘i ishlatiladi. DOCX qayta render qilinmaguncha taxminiy sahifa raqami fakt sifatida yozilmaydi.

## 4. Hisobot ko‘rsatkichlari

Leksik o‘xshashlik qamrovi taklifi:

`100 × mos deb belgilangan noyob token pozitsiyalari / hisobga olingan jami tokenlar`.

Turli manbalar qoplagan bir xil token bir marta sanaladi. Manba foizlarini qo‘shib umumiy foiz olinmaydi. Maxraj nol bo‘lsa «hisoblab bo‘lmaydi» ko‘rsatiladi. Exact va shingle dalillari alohida belgilanadi; ularning birlashmasi uchun ham takroriy sanash yo‘q.

Iqtibos, bibliografiya, titul va standart iboralar bo‘yicha xom va filtrlangan natija ajratiladi. Filtrlangan qismlar va sabablar ko‘rinadi. Dastlab avtomatik iqtibos tanish xatosiz deb olinmaydi. Akademiya yo‘nalishiga xos oyat, hadis, tarjima va keng tarqalgan ta’riflar alohida nazorat misollariga kiritiladi; ular avtomatik ayblov bo‘lmaydi.

Cosine similarity semantik ball sifatida ko‘rsatiladi, «plagiat foizi»ga aylantirilmaydi. Faqat annotatsiya solishtirilgan natija alohida ko‘rsatiladi va to‘liq manba tekshiruvi hisobiga qo‘shilmaydi. «Moslik topilmadi» — tekshirilgan korpus va olingan manbalar chegarasidagi natija.

## 5. Maxfiylik va xavfsizlik

- Ichki hujjatlar standart holatda tashqi xizmatlarga yuborilmaydi. Tashqi qidiruv jumla parchasini yuborsa ham axborot chiqishi hisoblanadi; alohida tasdiqlangan siyosat va foydalanuvchiga ko‘rinadigan rejim talab qilinadi.
- Real hujjatlarni ishlatishdan oldin to‘plash, indekslash, saqlash va parcha ko‘rsatish ruxsati qayd etiladi. Dastlab sun’iy yoki aniq ruxsatli namunalar ishlatiladi.
- Fayllar ommaviy web papkasidan tashqarida saqlanadi. Yuklash, ko‘rish, yuklab olish, hisobot va eksportda obyekt bo‘yicha ruxsat tekshiriladi.
- Hajm, parser vaqti/xotirasi, arxivning ochilish hajmi va parallel ishlar chegaralanadi. DOCX makroslari yoki PDF ichidagi dasturlar bajarilmaydi.
- Tashqi URL olishda ichki IP, localhost, metadata manzillari va xavfli redirectlar bloklanadi; hostlar ruxsat ro‘yxati bilan cheklanadi.
- Kalitlar muhit sozlamalarida; namunaviy sozlamalarda faqat placeholder. Loglarda kalit, to‘liq hujjat matni va maxfiy qidiruv parchalari bo‘lmaydi.
- Saqlash muddati, zaxira, o‘chirish tartibi, server joylashuvi va akademiya siyosati haqiqiy pilotdan oldin kelishiladi. Bu hujjat huquqiy muvofiqlikni tasdiqlamaydi.

## 6. MVP uchun yakuniy tekshiruv

Bir foydalanuvchi boshqasining hujjati yoki hisobotiga ID orqali kira olmasligi; exact nazorat parchasining topilishi; qoplash foizi 100 dan oshmasligi; skan PDF holatining to‘g‘ri chiqishi; cheklangan manbaning matni ochilmasligi; tashqi rejim o‘chiq bo‘lsa tashqariga so‘rov ketmasligi; xatolar va qamrovning ochiq ko‘rsatilishi talab qilinadi.

Ishlash tezligi va aniqlik uchun maqsad qiymatlar kompyuter, korpus va dastlabki o‘lchovlar aniqlangach belgilanadi. Hozircha o‘lchangan natijalar mavjud emas.
