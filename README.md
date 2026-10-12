# Islom akademiyasi uchun antiplagiat tizimi

O‘zbekiston xalqaro islom akademiyasining ruxsat bilan to‘plangan ilmiy hujjatlari va foydalanish huquqi tekshirilgan tashqi manbalar bilan matn o‘xshashligini aniqlash loyihasi.

**Holat:** lokal end-to-end hujjat solishtirish prototipi mavjud: Next.js interfeysidan TXT/DOCX/PDF yuklanadi, FastAPI leksik solishtiradi va mos parchalar bilan hisobot qaytaradi. `GET /health` va PostgreSQL uchun `GET /ready` saqlangan. Prototip autentifikatsiyasiz, akademiyada foydalanishga tayyor tizim emas. Quyidagi kelajak yechimlari boshlang‘ich taklif; akademiya tomonidan tasdiqlangan siyosat emas.

**Hujjat versiyasi:** 0.1 · **Sana:** 2026-10-12.

## Maqsad va chegaralar

Mos parchalar, ularning manbalari va tekshiruv qamrovini ko‘rsatadigan, BMI doirasida takrorlanuvchi tajribalar bilan baholanadigan platforma yaratish. O‘xshashlik foizi plagiatning avtomatik isboti emas. Yakuniy xulosani vakolatli inson beradi.

Butun internet, barcha ilmiy bazalar yoki yopiq nashrlar qamrab olinishi va’da qilinmaydi. Metama’lumot, annotatsiya, havola va amalda tahlil qilingan to‘liq matn alohida hisobga olinadi.

## Hujjatlar

| Fayl | Mazmun |
| --- | --- |
| [docs/requirements.md](docs/requirements.md) | Funksiyalar, rollar, maxfiylik va qabul mezonlari |
| [docs/architecture.md](docs/architecture.md) | Komponentlar, ma’lumotlar oqimi, algoritmlar va tashqi manbalar |
| [docs/roadmap.md](docs/roadmap.md) | Bosqichlar, tekshirish shartlari va BMI tajribalari |

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

Lokal solishtirish prototipi yaratildi: bitta tekshiriladigan hujjat va 1–5 ta yuklangan manba to‘liq solishtiriladi. Doimiy korpus, indeks, DB jadvali, login, tashqi qidiruv va semantik model yo‘q. `/health` faqat backend ishlayotganini bildiradi; `/ready` bazada `SELECT 1` bajaradi. Solishtirish uchun PostgreSQL talab qilinmaydi.

## Lokal hujjat solishtirish

Mavjud `.venv` uchun yangilangan aniq dependency ro‘yxatini o‘rnatish (Node/npm yoki Python qayta o‘rnatilmaydi):

```powershell
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Birinchi PowerShell oynasida backend:

```powershell
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Ikkinchi PowerShell oynasida frontend:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

Brauzerda `http://127.0.0.1:3000` ni oching. Bitta hujjat va 1–5 ta manba tanlang, **Solishtirish** ni bosing. Manbani va mos parchani tanlab ikki original matn, highlight hamda sahifa/paragraf raqamini ko‘ring. Fayllarni olib tashlash va qayta tanlash avvalgi hisobotni tozalaydi. Serverlarni o‘z oynalarida `Ctrl+C` bilan to‘xtating. Faqat loopback manzilida, bitta backend worker bilan ishlating; internetga ochmang.

Brauzer shu origin’dagi `/api/compare` ga `FormData` yuboradi; Next.js server marshruti uni lokal FastAPI `POST /compare` ga oqimli uzatadi. Standart backend manzili `http://127.0.0.1:8000`. Boshqa lokal port kerak bo‘lsa, frontendni ishga tushirishdan oldin `$env:ANTIPLAGIAT_API_URL = 'http://127.0.0.1:8001'` belgilang. Bu server sozlamasi; DB sozlamalari brauzerga uzatilmaydi. CORS ochilmagan, tashqi backend manzili va redirectlar qabul qilinmaydi. Same-origin va maxsus header tekshiruvi tashqi saytdan oddiy forma yuborishni cheklaydi; bu autentifikatsiya o‘rnini bosmaydi.

**Formatlar:** UTF-8 TXT (BOM mumkin), DOCX asosiy matni va jadvallari, matn qatlamli PDF. TXTda bo‘sh bo‘lmagan satr paragraf hisoblanadi. DOCX header/footer, izohlar va rasmlar olinmaydi; sahifa raqami taxmin qilinmaydi. PDFda haqiqiy sahifa raqami beriladi, lekin murakkab maketdagi o‘qish tartibi noto‘g‘ri bo‘lishi mumkin. Shifrlangan, buzilgan, bo‘sh, kamida bitta matnsiz sahifali PDF yoki qo‘llanmaydigan fayl xato holatini qaytaradi; 0% hisobot yaratilmaydi. OCR yo‘q.

**Chegaralar:** har fayl 10 MiB, jami fayl baytlari 30 MiB; multipart overhead uchun qo‘shimcha 64 KiB. Har hujjat 200 000 ajratilgan belgi, 30 000 token va kamida 5 token bilan cheklangan; PDF ko‘pi bilan 200 sahifa. DOCX arxivi ochilganda jami 50 MiB, 1000 element, asosiy XML esa 8 MiB gacha. Bir vaqtda bitta tekshiruv; yuklash 60 soniya, parser va solishtirish jarayoni 30 soniya, xotira 512 MiB. Windows Job Object xotira/CPU chegaralari yoqilmasa qayta ishlash rad etiladi. Bir hujjat–manba juftiga 300 000 solishtirish amali, manbaga 500 mos parcha va hisobotga 12 MiB chegara bor. Chegaradan oshganda natija kesib olinmaydi: tushunarli xato qaytariladi.

**Hisoblash:** Unicode NFKC, registr (`casefold`) va o‘zbek apostrof variantlari normallashtiriladi; tokenlar orasidagi bo‘shliq/tinish belgilari moslikka to‘sqinlik qilmaydi. 5 ketma-ket tokenli shingles tengligi tekshiriladi va moslik ikki tomondagi teng tokenlar bo‘ylab uzaytiriladi. Minimal parcha — 5 token. Original parcha belgima-belgi teng bo‘lsa `exact`, aks holda `shingle` deb beriladi. Umumiy leksik qoplash = mos kelgan **noyob** tekshiriluvchi token pozitsiyalari / barcha tekshiriluvchi tokenlar × 100; manba foizlari qo‘shilmaydi. Original ajratilgan matn va token → original koordinata xaritasi saqlanadi. Offsetlar noldan boshlanadigan Unicode code point `[start, end)` oraliqlari; frontend UTF-16 farqini hisobga oladi.

**Normalizatsiya siyosati `uz-latin-v2`:** yuqoridagi NFKC/registr/apostrof qoidalariga qo‘shimcha ravishda faqat U+200B (ZWSP), U+00AD (soft hyphen), U+200C (ZWNJ) va U+FEFF belgilaridan iborat ketma-ketlik bevosita ikki lotin harfi orasida bo‘lsa solishtirish nusxasida tashlab ketiladi. Harf Unicode `L*` kategoriyasi va nomidagi `LATIN` bilan aniqlanadi; birikuvchi urg‘u orqali qo‘shni harfni qidirish yo‘q. Original ajratilgan matn va offsetlar o‘zgarmaydi. Barcha Cf/Mn belgilarini global o‘chirish yo‘q; arab va boshqa yozuvlardagi join-control belgilariga bu qoida qo‘llanmaydi. Matn boshi/oxiri, bo‘shliq yoki tinish belgisi yonidagi ketma-ketlik saqlanadi. Siyosat versiyasi hisobotning `parameters.normalization_version` maydonida, qoida qo‘llangani haqidagi ogohlantirish esa `limitations` va frontendda ko‘rinadi. Farqli original parchalar normallashtirilgan `shingle` deb belgilanadi.

ZWSP ba’zan haqiqiy so‘z chegarasi bo‘ladi: masalan, `bir<U+200B>ikki` bu evristikada `birikki` tokeniga aylanishi mumkin. Siyosat dastlabki o‘zbek lotin matnlari uchun tor evristika; barcha Unicode chetlab o‘tishlarini hal qilmaydi. Arab harakatlari yashirin olib tashlanmaydi va yangi arab normalizatsiyasi qo‘shilmagan. Unicode nomi `ARABIC` bo‘lgan `M*` belgilar hujjat yoki manbada aniqlansa, hisobotda **arab harakatlari bo‘yicha tokenizatsiya hali ishonchli emas; moslik va umumiy ko‘rsatkich ehtiyotkor talqin qilinishi kerak** degan ogohlantirish chiqadi. Arab tili to‘liq qo‘llab-quvvatlanishi tasdiqlanmagan.

**Cheklovlar:** o‘xshashlik plagiatning avtomatik isboti emas. Iqtibos/bibliografiya filtri yo‘q. “Moslik topilmadi” faqat yuklangan manbalar doirasida. Parafraz yoki semantik o‘xshashlik aniqlangan deb da’vo qilinmaydi; indekslash keyingi bosqich. Bitta manba yaroqsiz bo‘lsa butun so‘rov xato bilan tugaydi, yashirin qisman hisobot yo‘q.

Fayllar OS vaqtinchalik katalogida tasodifiy katalog va server bergan nomlar bilan ishlanadi. Foydalanuvchi fayl nomi disk yo‘li sifatida ishlatilmaydi. Muvaffaqiyat, parser/yuklash xatosi va timeoutda katalog tozalanadi. Jarayon yoki kompyuter majburan o‘chirilgandagi disk qoldiqlarini yo‘qotish kafolatlanmaydi; bu xavfsiz o‘chirish tizimi emas. Hisobot brauzer xotirasida qoladi. Hujjatlar internetga yuborilmaydi; kod matn yoki maxfiy qiymatlarni loglamaydi. Parser worker stdout/stderr va logging chiqishlari bostirilgan. Hujjat matni React text node sifatida render qilinadi, HTML sifatida bajarilmaydi.

Yangi dependencylar (mavjudlari yangilanmagan):

| Paket | Versiya | Litsenziya va moslik |
| --- | --- | --- |
| [pypdf](https://pypi.org/project/pypdf/6.20.0/) | 6.20.0 | BSD-3-Clause; Python 3.14 klassifikatori, sof Python PDF parser |
| [defusedxml](https://pypi.org/project/defusedxml/0.7.1/) | 0.7.1 | PSFL; DOCX XMLda DTD/entity va tashqi resurslarni bloklash; 3.14 mosligi lokal test bilan tekshirildi |
| [python-multipart](https://pypi.org/project/python-multipart/0.0.32/) | 0.0.32 | Apache-2.0; Python 3.14 klassifikatori; hajmi chegaralangan oqimli yuklash |

DOCX uchun `zipfile` + `defusedxml` tanlandi: matn ajratishga yetarli va qo‘shimcha lxml dependency’si talab qilmaydi. Yangi parserlar Python 3.14.3 dagi mavjud muhitda sinovdan o‘tdi; yangilangan to‘liq requirements bilan toza muhitdan qayta o‘rnatish hali tekshirilmagan.

Tekshiruv buyruqlari:

```powershell
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
Set-Location D:\aniplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe scripts/check_e2e.py
```

`check_e2e.py` faqat sun’iy namunalar bilan haqiqiy HTTP orqali production frontend → backend → worker → hisobot oqimini tekshiradi. Bo‘sh loopback portlaridan foydalanadi, o‘z serverlarini to‘xtatadi va vaqtinchalik ma’lumotlarini tozalaydi. PostgreSQLga ulanmaydi; `/ready` konfiguratsiyasiz 503 bo‘lishi tekshiriladi. Mock DB testlari haqiqiy DB testi deb hisoblanmaydi. Backendning 29 ta unittest’i (shu jumladan 7 readiness regressiya testi), haqiqiy worker xotira/timeout testlari va `pip check` muvaffaqiyatli o‘tdi. Yangi regressiyalar to‘rtta ko‘rinmas belgi va ularning ketma-ketligi, chegaralar, boshqa yozuvlar, original highlight/exact yorlig‘i, Unicode/apostrof/urg‘u, arab ogohlantirishi va policy’dan olinadigan kasrli timeout xabarini qamraydi. Timeout xabari qiymatlari mock worker bilan; workerning haqiqiy to‘xtashi alohida testda tekshiriladi.

## Frontendni ishga tushirish va tekshirish

`frontend/` — Next.js App Router, TypeScript va ESLint asosidagi alohida npm loyiha. Bosh sahifa tili `uz`; oddiy CSS va tizim shriftlari ishlatiladi. Yuklash, olib tashlash, kutish, xato, manba/parcha tanlash va haqiqiy hisobot holatlari mavjud. Desktop uchun ikki ustunli, mobil uchun bir ustunli CSS ishlatiladi. Tashqi font/CDN, Tailwind, UI kutubxonasi, React Compiler va login yo‘q.

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
Set-Location D:\aniplagiat\frontend
npm.cmd ci
```

Ishlab chiqish serveri:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

3000-port band bo‘lsa, boshqa bo‘sh portni tanlang. Serverni o‘sha oynada `Ctrl+C` bilan to‘xtating.

Tekshiruvlar va production build:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
```

Production builddan keyin bo‘sh lokal portni tanlab ishga tushirish:

```powershell
Set-Location D:\aniplagiat\frontend
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$frontendPort = $listener.LocalEndpoint.Port
$listener.Stop()
Write-Host "Frontend: http://127.0.0.1:$frontendPort"
npm.cmd run start -- --hostname 127.0.0.1 --port $frontendPort
```

Ikkinchi PowerShell oynasida chiqarilgan portni kiriting va HTTP javobini tekshiring:

```powershell
Set-Location D:\aniplagiat\frontend
$frontendPort = Read-Host 'Server oynasidagi port'
$response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$frontendPort/"
$response.StatusCode
$response.Content -match 'Islom akademiyasi — Antiplagiat'
```

Kutiladigan natija: `200` va `True`. Sinov tugagach server oynasida `Ctrl+C` bosing. `node_modules/`, `.next/` va TypeScript build keshi Git’dan chetlashtirilgan.

Mustaqil reviewda desktop va 375×812 mobil brauzer oqimi, hisoblash, original koordinatalar, Windows resurs chegaralari hamda timeout/tozalash tekshirilgan. Bu review natijasi; joriy tuzatishlarda brauzer oqimi qayta tekshirilmadi. Ilmiy benchmark va haqiqiy murakkab Word/PDF hujjatlaridagi extraction/matching sifati hali baholanmagan.

Review tuzatishlaridan keyin mavjud muhitda ESLint, TypeScript, production build va 27 ta haqiqiy HTTP tekshiruvi o‘tdi. Frontend → FastAPI → haqiqiy worker orqali to‘rtta ko‘rinmas belgi, ketma-ketlik, normalizatsiya versiyasi, original offsetlar va arab harakatlari bor/yo‘q ogohlantirishlari ham tekshirildi. Skript yaratgan loopback serverlari to‘xtatildi va vaqtinchalik yuklash kataloglari qolmagani tekshirildi. Yangi yuklama testi, katta audit yoki toza muhitdan o‘rnatish bajarilmadi.

O‘rnatishdagi npm audit ESLint dependency zanjirida 5 ta yuqori darajadagi topilmani ko‘rsatdi (`braces` orqali); avtomatik majburiy downgrade qo‘llanmadi. `npm.cmd audit --omit=dev` esa 0 ta zaiflik ko‘rsatdi. Generator tanlagan ESLint 9.39.5 uchun npm qo‘llab-quvvatlash muddati tugaganligi haqida ogohlantirdi.

## Backendni ishga tushirish va tekshirish

Faqat toza checkoutda, `.venv` hali mavjud bo‘lmasa, Python 3.14 orqali virtual muhit yarating va backend paketlarini o‘rnating. Quyidagi tayyorlash buyruqlarini mavjud `.venv` ustida bajarmang:

```powershell
Set-Location D:\aniplagiat
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Oldingi 14 paketli backend ro‘yxati toza Python 3.14.3 muhitida tekshirilgan. Psycopg qo‘shilgan joriy ro‘yxatni toza muhitdan qayta o‘rnatish hali tekshirilmagan.

PowerShell’da loyiha ildizidan (`D:\aniplagiat`), mavjud `.venv` orqali:

```powershell
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Ikkinchi PowerShell oynasida haqiqiy HTTP javobini tekshirish:

```powershell
Set-Location D:\aniplagiat
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
