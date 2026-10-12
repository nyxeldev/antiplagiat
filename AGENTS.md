# Loyiha bo‘yicha agent ko‘rsatmalari

## Ish doirasi

- Har safar bitta kelishilgan vazifani bajaring; natijasi tekshirilmaguncha keyingi bosqichga o‘tmang.
- Tahrirdan oldin Git holati, tegishli mavjud fayllar va shu papkaga tegishli ko‘rsatmalarni o‘qing.
- Boshqa ishchi o‘zgarishlarni saqlang; vazifaga aloqasiz fayllarni tahrirlamang yoki qaytarmang.
- Yo‘l xaritasidagi kelajak vazifalarini joriy topshiriq deb qabul qilmang.

## Hujjatlar va muhit

Vazifaga tegishli manbalarni tanlab o‘qing; har kichik tahrirda barcha hujjatlarni qayta o‘qish shart emas:

- [README](README.md) — amaldagi holat, muhit va bajarish buyruqlari.
- [Talablar](docs/requirements.md) — doira, ruxsatlar, maxfiylik va qabul mezonlari.
- [Arxitektura](docs/architecture.md) — komponentlar, ma’lumotlar oqimi va qarorlar.
- [Yo‘l xaritasi](docs/roadmap.md) — bosqichlar va tajribalar rejasi.
- [Frontend README](frontend/README.md) — frontendni ishlatish va tekshirish.

- Buyruqlar Windows PowerShell 5.1 bilan mos bo‘lsin; ishchi papkani `Set-Location` bilan aniq ko‘rsating.
- Python uchun loyiha ildizidagi `.venv\Scripts\python.exe` interpreteridan foydalaning.
- npm buyruqlarida zarur bo‘lsa `npm.cmd` ishlating; muhitni tekshirmay qayta o‘rnatmang.
- Versiyalar va bajarish buyruqlari uchun [backend/requirements.txt](backend/requirements.txt), [frontend/package.json](frontend/package.json), [frontend/package-lock.json](frontend/package-lock.json) va README’ga tayaning.
- O‘zgaruvchan texnologiya versiyalarini ushbu faylda takrorlamang; dependency o‘zgarsa lockfile mosligini saqlang.

## Ma’lumotlar va o‘zgarishlar

- Maxfiy kalit va parollarni kod, Git, log yoki javobga chiqarmang.
- Vazifa talab qilmasa haqiqiy `.env` va maxfiy hujjatlarni ochmang; `.env.example` faqat namuna.
- Testlarda sun’iy yoki foydalanishga aniq ruxsat berilgan ma’lumotlardan foydalaning.
- Metama’lumot, annotatsiya va amalda tahlil qilingan to‘liq matnni ajrating.
- Matn o‘xshashligini avtomatik plagiat hukmi deb bermang; qamrov va cheklovlarni ko‘rsating.
- Arxitektura yoki dependencydagi katta o‘zgarishning sababi va ta’sirini izohlang.
- Audit topilmalarini yashirish uchun majburiy downgrade yoki `--force` ishlatmang.

## Tekshiruv va hamkorlik

- Vazifaga mos tekshiruvlarni bajaring; mock, haqiqiy HTTP, haqiqiy DB va brauzerdagi vizual tekshiruvni aniq ajrating.
- Bajarilmagan testni o‘tdi deb yozmang; muvaffaqiyatsizlik va tekshiruv chegaralarini ochiq qayd eting.
- Aniq sabab bo‘lmasa to‘liq testlarni qayta-qayta, yuklama testini yoki katta auditni ishga tushirmang.
- Faqat o‘zingiz yaratgan vaqtinchalik fayllarni tozalang va o‘zingiz ishga tushirgan jarayonlarni to‘xtating.
- Bir xil fayllarni ikki agentga nazoratsiz parallel tahrirlatmang.
- Codex odatda implementatsiya, Claude Code mustaqil review uchun ishlatiladi; joriy vazifada berilgan rol ustun.
- Faqat review so‘ralganda fayllarni tahrirlamang; topilmalarni dalil va fayl joyi bilan bering.
- Commitlarni mantiqiy bosqichlarga ajrating; commit, push yoki deployni faqat joriy topshiriq ruxsat berganda bajaring.
- Yakuniy hisobotda o‘zgarishlar, bajarilgan tekshiruvlar, haqiqiy natijalar va qolgan cheklovlarni yozing.
