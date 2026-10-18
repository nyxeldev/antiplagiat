# Loyiha bo‘yicha agent ko‘rsatmalari

## Ish doirasi

- Har safar bitta kelishilgan vazifani bajaring; natijasi tekshirilmaguncha keyingi bosqichga o’tmang.
- Tahrirdan oldin Git holati, tegishli mavjud fayllar va shu papkaga tegishli ko’rsatmalarni o’qing.
- Boshqa ishchi o’zgarishlarni saqlang; vazifaga aloqasiz fayllarni tahrirlamang yoki qaytarmang.
- Yo’l xaritasidagi kelajak vazifalarini joriy topshiriq deb qabul qilmang.

## Ish qoidalari

- Minimal o‘zgarish: topshiriq doirasidan tashqaridagi faylga tegma, "yo‘l-yo‘lakay" yaxshilash qilma.
- 2 urinish qoidasi: bir xil muammoni ikki marta hal qila olmasang — to‘xta, nima sinaganingni va nimaga ishlamaganini yozib, mendan so‘ra. Uchinchi urinishni qilma.
- Graf (graphify) — yordamchi xarita, haqiqat manbai emas. Fayl tahrir qilingandan keyin graf eskirgan bo‘lishi mumkin. Tahrirdan oldin grafdan olingan har qanday xulosani haqiqiy fayl mazmuni bilan tasdiqla.

## Hech qachon

- rm -rf, Remove-Item -Recurse -Force (loyiha fayllariga)
- git reset --hard, git checkout -- ., git clean -fd
- DROP TABLE / DROP DATABASE / TRUNCATE
- mavjud `antiplagiat` klasteriga migratsiya qo‘llash (faqat disposable klaster)
- npm/pip uchun --force yoki majburiy downgrade
- .env, .env.* yoki backend/.env faylini o‘qish
- push, deploy
- mavjud testni o‘chirish yoki yumshatish

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

## Buyruqlar

Har bir vazifa uchun quyidagi buyruqlar mavjud. **Ishchi papkani** (`Set-Location` bilan) **ko'rsatilishi kerak**:

| Buyruq | Vazifasi | Ishchi papka |
|--------|---------|---------------|
| `.\.venv\Scripts\python.exe -m backend.manage migrate --check` | Migratsiya read-only diagnostika (DDL yo'q) | `D:\antiplagiat` |
| `.\.venv\Scripts\python.exe -m backend.manage migrate` | Migratsiyani qo'llash (vakolatli DB hisobi so'raladi) | `D:\antiplagiat` |
| `.\.venv\Scripts\python.exe -m backend.manage create-user <login>` | Hisob yaratish (parol yashirin so'raladi) | `D:\antiplagiat` |
| `.\scripts\start_backend.ps1` | Backend ishga tushirish (yashirin DB parol so'rash) | `D:\antiplagiat` |
| `npm.cmd run dev -- --hostname 127.0.0.1 --port 3000` | Frontend ishlab chiqish serveri | `D:\antiplagiat\frontend` |
| `.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v` | Backend unittest (mock + real disposable Postgres) | `D:\antiplagiat` |
| `.\.venv\Scripts\python.exe -m pip check` | Paket mosligini tekshirish | `D:\antiplagiat` |
| `npm.cmd run lint` | Frontend ESLint tekshiruvi | `D:\antiplagiat\frontend` |
| `npm.cmd run typecheck` | Frontend TypeScript tekshiruvi | `D:\antiplagiat\frontend` |
| `npm.cmd run build` | Frontend production build | `D:\antiplagiat\frontend` |
| `.\.venv\Scripts\python.exe scripts/check_e2e.py` | E2E HTTP + disposable Postgres | `D:\antiplagiat` |
| `.\.venv\Scripts\python.exe scripts\eval_retrieval.py` | Retrieval/matching eval harness (disposable Postgres) | `D:\antiplagiat` |
| `graphify extract . --code-only --no-viz --force` | Bilimlar grafini qayta qurish (AST, LLM yo'q) | `D:\antiplagiat` |

**To'liq tafsilot:** [README.md § Tekshiruv buyruqlari](README.md#tekshiruv-buyruqlari).

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
