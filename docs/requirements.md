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

**Amaldagi holat:** `users.role` ustuni `user/reviewer/corpus_manager/admin` qiymatlarini qabul qiladi. `admin` va `corpus_manager` — ikkalasi ham korpusni boshqaradi (`backend/auth.py`dagi `CORPUS_MANAGEMENT_ROLES`); `corpus_manager` boshqa hech qanday qo‘shimcha huquqqa ega emas, faqat shu bitta amal uchun. `reviewer` hozircha oddiy foydalanuvchi bilan bir xil. Administrator va `corpus_manager` ham **boshqa foydalanuvchining shaxsiy hisobotini ko‘rmaydi**; bu qoida korpus bosqichida ham o‘zgarmadi.

**Rol matritsasi (koddagidek):**

| Rol | Korpus boshqaruvi (`/corpus/documents*`) | Shaxsiy hisobotlar |
| --- | --- | --- |
| `admin` | 200 | Faqat o‘ziniki |
| `corpus_manager` | 200 | Faqat o‘ziniki |
| `user` | 403 | Faqat o‘ziniki |
| `reviewer` | 403 | Faqat o‘ziniki |
| (login yo‘q) | 401 | 401 |

### 2.1 Ichki korpus ruxsat modeli

- Korpusga hujjat qo‘shish, ro‘yxatini ko‘rish va chiqarish (withdraw) — `admin` yoki `corpus_manager`. Autentifikatsiyasiz so‘rov 401, bu ikki roldan boshqa sessiya 403 oladi.
- Har bir korpus hujjati uchun **ruxsat asosi (`permission_basis`) majburiy**; u bo‘sh bo‘lsa hujjat umuman saqlanmaydi. Ruxsat asosi keyinchalik o‘zgartirilmaydi (DB triggeri taqiqlaydi).
- Oddiy foydalanuvchi korpus manbasidan **to‘liq matnni hech qachon olmaydi**: faqat metama’lumot, mos kelgan parcha va har tomondan cheklangan kontekst (`<=200` belgi), hisobot bo‘yicha umumiy kontekst budjeti bilan.
- Shaxsiy tekshiruv hujjatlari va hisobot matnlari **avtomatik korpusga qo‘shilmaydi**. Korpusga kirish faqat adminning aniq amali bilan bo‘ladi.
- Korpus tekshiruvi **opt-in**: solishtirish so‘rovidagi ixtiyoriy bayroq, default o‘chiq.
- Withdraw qilingan hujjatning matni va chunk matnlari o‘chiriladi; qidiruvdan chiqadi. Faqat minimal yozuv (ID, ruxsat asosi, digest, sana) dalil sifatida qoladi. Bu WAL/zaxiradagi izlarning xavfsiz yo‘qotilishi emas.

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

### 5.1 Ichki korpus uchun qo‘shimcha shartlar

- Runtime DB hisobiga korpus jadvallarida faqat `SELECT`/`INSERT` va ustun darajasidagi `UPDATE` beriladi; `DELETE`, DDL va `PUBLIC` huquqlari yo‘q. Shuning uchun ilova dalilni qattiq o‘chira olmaydi.
- Yuklangan binar fayl doimiy saqlanmaydi; faqat ajratilgan matn, uning chunklari va `content_sha256` qoladi.
- Bir xil fayl (`content_sha256`) faol holatda ikki marta kiritilmaydi; takror yuklash aniq xato bilan rad etiladi.
- Korpus matni faqat parserning sandboxlangan worker jarayonida ajratiladi; worker DB ma’lumotlarini olmaydi, korpus so‘rovlari esa faqat ota jarayonda bajariladi.

## 6. MVP uchun yakuniy tekshiruv

Bir foydalanuvchi boshqasining hujjati yoki hisobotiga ID orqali kira olmasligi; exact nazorat parchasining topilishi; qoplash foizi 100 dan oshmasligi; skan PDF holatining to‘g‘ri chiqishi; cheklangan manbaning matni ochilmasligi; tashqi rejim o‘chiq bo‘lsa tashqariga so‘rov ketmasligi; xatolar va qamrovning ochiq ko‘rsatilishi talab qilinadi.

Ishlash tezligi va aniqlik uchun maqsad qiymatlar kompyuter, korpus va dastlabki o‘lchovlar aniqlangach belgilanadi. Hozircha o‘lchangan natijalar mavjud emas.
