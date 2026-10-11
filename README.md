# Islom akademiyasi uchun antiplagiat tizimi

O‘zbekiston xalqaro islom akademiyasining ruxsat bilan to‘plangan ilmiy hujjatlari va foydalanish huquqi tekshirilgan tashqi manbalar bilan matn o‘xshashligini aniqlash loyihasi.

**Holat:** boshlang‘ich hujjatlar va minimal FastAPI backend (`GET /health`) mavjud. Windows muhiti tekshirilgan. Frontend va API integratsiyalari hali yaratilmagan. Quyidagi yechimlar boshlang‘ich taklif; akademiya tomonidan tasdiqlangan siyosat emas.

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

Next.js + TypeScript; Python + FastAPI; PostgreSQL va uning full-text search imkoniyatlari. Sentence Transformers va pgvector semantik tajribalardan keyin qo‘shiladi. Redis, Celery va OpenSearch zarurati o‘lchovlar bilan asoslanadi. Git versiyalar nazorati uchun ishlatiladi. Aniq versiyalar mavjud muhit tekshirilgach tanlanadi.

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

Minimal FastAPI backend va `GET /health` endpointini haqiqiy HTTP so‘rovi bilan tekshirish. Endpoint faqat backend ishlayotganini bildiradi; ma’lumotlar bazasiga ulanmaydi va uning tayyorligini tekshirmaydi.

## Backendni ishga tushirish va tekshirish

Faqat toza checkoutda, `.venv` hali mavjud bo‘lmasa, Python 3.14 orqali virtual muhit yarating va backend paketlarini o‘rnating. Quyidagi tayyorlash buyruqlarini mavjud `.venv` ustida bajarmang:

```powershell
Set-Location D:\aniplagiat
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Toza muhitdan qayta o‘rnatish hali sinovdan o‘tmagan.

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

## Hali aniqlanmagan ma’lumotlar

Kompyuter xususiyatlari va o‘rnatilgan dasturlar; loyiha joylashuvi; BMI muddati; korpus hajmi va undan foydalanish ruxsati; hosting; tashqi API byudjeti; saqlash muddati va akademiyaning yakuniy rollar siyosati. Bular fakt sifatida taxmin qilinmaydi.
