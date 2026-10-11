# Islom akademiyasi uchun antiplagiat tizimi

O‘zbekiston xalqaro islom akademiyasining ruxsat bilan to‘plangan ilmiy hujjatlari va foydalanish huquqi tekshirilgan tashqi manbalar bilan matn o‘xshashligini aniqlash loyihasi.

**Holat:** 0-bosqich — boshlang‘ich hujjatlar. Dastur, ma’lumotlar bazasi va API integratsiyalari hali yaratilmagan. Windows muhiti tekshirilmagan. Quyidagi yechimlar boshlang‘ich taklif; akademiya tomonidan tasdiqlangan siyosat emas.

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

Ushbu to‘rtta hujjatni o‘qib, boshlang‘ich doira tushunarli ekanini tekshirish. Hozir o‘rnatish, serverni ishga tushirish yoki dastur kodi yozish talab qilinmaydi. Hujjatlar ko‘rib chiqilgach, keyingi alohida qadam Windows muhiti va loyiha uchun papkani aniqlash bo‘ladi.

## Hali aniqlanmagan ma’lumotlar

Kompyuter xususiyatlari va o‘rnatilgan dasturlar; loyiha joylashuvi; BMI muddati; korpus hajmi va undan foydalanish ruxsati; hosting; tashqi API byudjeti; saqlash muddati va akademiyaning yakuniy rollar siyosati. Bular fakt sifatida taxmin qilinmaydi.
