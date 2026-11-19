# Ishlatish bo'yicha qo'llanma (production)

Bu fayl **qanday qilish kerak** (operatsion tartib) haqida; **nima uchun shunday qaror qilindi** `docs/decisions.md`da (§13-dan boshlab, FAZA 4). Server hali tanlanmagan, shuning uchun bu yerdagi barcha ko'rsatmalar muhitdan mustaqil — faqat Windows + PostgreSQL + Python/Node.js talab qiladi.

## 1. Majburiy konfiguratsiya

Backend quyidagi muhit o'zgaruvchilarisiz **ishga tushmaydi** (`backend/main.py`dagi `lifespan`, `docs/decisions.md` §14):

| O'zgaruvchi | Misol | Izoh |
| --- | --- | --- |
| `ANTIPLAGIAT_DB_HOST` | `127.0.0.1` | |
| `ANTIPLAGIAT_DB_PORT` | `5432` | |
| `ANTIPLAGIAT_DB_NAME` | `antiplagiat` | |
| `ANTIPLAGIAT_DB_USER` | `antiplagiat_app` | Runtime (kam huquqli) rol — migratsiya hisobi emas |
| `ANTIPLAGIAT_DB_PASSWORD` | — | |
| `ANTIPLAGIAT_PUBLIC_ORIGIN` | `http://127.0.0.1:3000` (lokal) yoki `https://<host>` | Yo'q bo'lsa lokal HTTP defaultga tushadi (xavfsiz); **noto'g'ri** qiymat bilan to'xtaydi |

To'liq namuna (maxfiy qiymatsiz): `.env.example` — loyihada allaqachon mavjud, lekin bu agent sessiyasining xavfsizlik sozlamalari `.env*` naqshidagi fayllarni o'qish/yozishni butunlay taqiqlagani uchun uni to'g'ridan-to'g'ri tahrirlay olmadim. Fayl allaqachon to'liq bo'lsa, tasdiqlang; aks holda quyidagi tarkibni o'zingiz `.env.example`ga joylashtiring (frontend tomoni uchun ikkita qo'shimcha o'zgaruvchi, `ANTIPLAGIAT_API_URL` va `ANTIPLAGIAT_PUBLIC_ORIGIN`, `frontend/lib/proxy.ts`da ishlatiladi):

```
# Backend runtime DB hisobi (kam huquqli; migratsiya hisobi emas)
ANTIPLAGIAT_DB_HOST=127.0.0.1
ANTIPLAGIAT_DB_PORT=5432
ANTIPLAGIAT_DB_NAME=antiplagiat
ANTIPLAGIAT_DB_USER=antiplagiat_app
ANTIPLAGIAT_DB_PASSWORD=

# Frontend <-> backend (ikkisi ham shu qiymatlarni o'qiydi)
ANTIPLAGIAT_PUBLIC_ORIGIN=http://127.0.0.1:3000
ANTIPLAGIAT_API_URL=http://127.0.0.1:8000
```

**Topilgan va ko'rib chiqilgan defaultlar (FAZA 4 auditi):**
- `ANTIPLAGIAT_PUBLIC_ORIGIN` (backend `backend/auth.py` va frontend `frontend/lib/proxy.ts`) — yo'q bo'lsa `http://127.0.0.1:3000`ga tushadi. **Xavfsiz**: faqat lokal host, arxitektura bo'yicha tizim shu doiradan tashqariga ochilmaydi (`auth.guard()`, `proxy.ts`).
- `ANTIPLAGIAT_API_URL` (frontend) — yo'q bo'lsa `http://127.0.0.1:8000`ga tushadi. **Xavfsiz**, xuddi yuqoridagi sabab bilan; `proxy.ts` baribir faqat `http://127.0.0.1|localhost` qabul qiladi.
- `MIN_PASSWORD_CHARS` (`backend/manage.py`) — **xavfsiz emas** edi (4, 2026-10dagi lokal sinov uchun yengillik). Tuzatildi: §13.
- Boshqa joyda muhitdan o'qiladigan/defaultli maxfiy qiymat topilmadi (`os.environ.get(..., "...")` butun repo bo'yicha qidirildi).

## 2. Zaxira nusxa olish va tiklash

### Zaxira olish

```powershell
$env:PGPASSWORD = '<migratsiya hisobi paroli>'
& 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe' -h 127.0.0.1 -p 5432 -U <migratsiya_hisobi> -d antiplagiat -n antiplagiat -Fc -f "antiplagiat-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
```

- `-Fc` (custom format) — siqilgan, `pg_restore` bilan selektiv tiklashga imkon beradi.
- `-n antiplagiat` — faqat ilova sxemasi (PostgreSQLning o'z `postgres`/`template1` baza-darajasidagi ob'ektlari kerak emas).
- Migratsiya hisobidan foydalaniladi (runtime `antiplagiat_app` hisobida bu uchun yetarli huquq yo'q, va bo'lishi ham shart emas).

**Davriylik tavsiyasi:** kundalik avtomatik (Windows Task Scheduler orqali, bu skript emas — alohida, operator tomonidan sozlanadigan vazifa) + har qanday katta korpus import/migratsiyadan OLDIN qo'lda. **Saqlash joyi:** ilova serveridan FIZIK ALOHIDA joy (tashqi disk, tarmoq ulashmasi yoki bulut ob'ekt saqlash) — bitta diskning o'zi zaxira emas.

### Tiklash

```powershell
$env:PGPASSWORD = '<migratsiya hisobi paroli>'
& 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' -h 127.0.0.1 -p 5432 -U <migratsiya_hisobi> -d antiplagiat --no-owner --clean --if-exists "antiplagiat-<sana>.dump"
```

`antiplagiat_app` roli maqsad klasterda OLDINDAN mavjud bo'lishi kerak (`CREATE ROLE antiplagiat_app LOGIN PASSWORD '...' NOSUPERUSER NOCREATEDB NOCREATEROLE;`) — dump faqat `antiplagiat` sxemasini tiklaydi, rollarni emas.

### AMALDA sinalgan natija (2026-11-09)

Haqiqiy, egalik qilingan, bir-biridan mustaqil IKKI disposable PostgreSQL klaster bilan sinaldi (`backend/tests/postgres_fixture.py`dagi bir xil naqsh, haqiqiy foydalanuvchi bazasiga umuman tegilmadi):
1. Klaster A: migratsiya qo'llanildi (7 ta migratsiya), 1 foydalanuvchi, 1 korpus hujjati, 1 hisobot yaratildi.
2. `pg_dump -Fc` bilan 32 065 baytlik zaxira olindi.
3. Klaster B — **butunlay bo'sh, hech qachon migratsiya qo'llanmagan** — yaratildi.
4. `pg_restore --no-owner` bilan zaxiradan tiklandi.
5. Tasdiqlandi: `schema_migrations` 7/7 mos (versiya+checksum), `users`/`corpus_documents`/`reports` soni va aniq identifikatorlari to'liq mos, VA runtime rolining `corpus_excerpt_audit`dagi kabi cheklangan huquqlari (bu holatda `corpus_documents`ga DELETE huquqi yo'qligi) tiklangan bazada ham saqlanganligi tasdiqlandi — GRANT/REVOKE holati dumpning o'zida saqlanadi, qayta qo'lda bajarish kerak emas.

**Xulosa: sinalmagan zaxira zaxira emas degan talab bajarildi — bu aniq ikki klasterli sinov haqiqiy `pg_dump`/`pg_restore` ikkilik fayllari bilan ishladi, mock emas.**

## 3. Loglar

Hozircha ilovada alohida fayl-logging qatlami yo'q (`logging.basicConfig` chaqirilmaydi) — backend jarayoni `uvicorn`ning o'z access/error logini, frontend esa `next start`ning o'z chiqishini **stdout/stderr**ga yozadi. Bu FAZA 4 doirasida ataylab o'zgartirilmadi (logging freymvorki qo'shish bu bosqichning maqsadidan tashqarida); o'rniga quyidagilar tekshirildi va hujjatlashtirildi:

- **Maxfiy qiymat yo'qligi tasdiqlandi:** parol/token hech qachon `print`/logger chaqiruviga uzatilmaydi (`backend/persistence.py` xom driver xatolarini saniatizatsiya qiladi; `backend/manage.py`ning diagnostikasi faqat oq ro'yxatdagi metadata chiqaradi; argon2 xato xabarlari parolni o'z ichiga olmaydi). `uvicorn`ning standart access-log format satri faqat `client_addr`, `method`, `path+query`, `status`ni o'z ichiga oladi — **hech bir endpoint maxfiy qiymatni query string orqali qabul qilmaydi** (parol/token har doim POST tanasi yoki cookie'da), shuning uchun access-log yoqilgan holatda ham xavfsiz.
- **Qayerga yozish va aylantirish (rotation):** Python logging modulining o'zi ishlatilmagani uchun fayl-aylantirish ilova darajasida emas, **xizmat o'rami darajasida** amalga oshiriladi (§4dagi NSSM misoli `AppStdout`/`AppStderr`ni faylga yo'naltiradi va NSSMning o'z `AppRotateBytes`/`AppRotateSeconds` sozlamalari orqali aylantiradi — kod o'zgarishi shart emas). Muhim bo'lmagan: PostgreSQLning o'z logi (`pg_log`) PostgreSQL o'rnatmasining standart joylashuvi va aylantirish siyosati bo'yicha alohida boshqariladi.

## 4. Audit jurnalini tozalash

`antiplagiat.corpus_excerpt_audit` yozuvlari hech qachon avtomatik o'chirilmaydi (append-only runtime huquqi — `docs/decisions.md` §2/§13). Tavsiya etilgan ~12 oylik saqlash muddatini amalga oshirish uchun, **qo'lda**, migratsiya hisobi bilan:

```powershell
.\.venv\Scripts\python.exe -m backend.manage audit-cleanup --older-than-days 365
```

Cron yoki Windows Task Scheduler talab qilinmaydi (ataylab — buyruq operator tomonidan ongli ravishda ishga tushiriladi); xohlasa operator buni o'zi davriy vazifaga bog'lashi mumkin, lekin bu loyihaning o'z majburiyati emas.

## 5. Production rejimida ishga tushirish

### Backend

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**`--workers 1` ataylab:** `backend/comparison/api.py` va `backend/corpus_api.py`dagi `gate`/`login_gate` kabi ichki-protsess qulflar (`threading.Lock`/`BoundedSemaphore`) BIR Python protsessi doirasida ishlaydi — bir nechta uvicorn worker protsessi ularni baham ko'rmaydi, demak ko'p workerli rejim bu himoyalarni amalda o'chirib qo'yadi. Ko'proq tashqi parallel yuklamaga chidam kerak bo'lsa, bir nechta BACKEND PROTSESSINI alohida portlarda va oldida load balancer bilan ishga tushirish kerak bo'ladi (bu alohida, o'lchangan qaror, bu bosqichda qilinmaydi) — `--workers`ni ko'paytirish emas.

### Frontend

```powershell
Set-Location D:\antiplagiat\frontend
npm.cmd ci
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

### Windows'da xizmat sifatida yurgizish (tavsiya)

Skript yozilmadi (operator muhitiga bog'liq ko'p tafsilot bor); tavsiya etilgan, takrorlanadigan yondashuv — [NSSM](https://nssm.cc/) (Non-Sucking Service Manager):

```powershell
nssm install AntiplagiatBackend "D:\antiplagiat\.venv\Scripts\python.exe" "-m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1"
nssm set AntiplagiatBackend AppDirectory "D:\antiplagiat"
nssm set AntiplagiatBackend AppEnvironmentExtra "ANTIPLAGIAT_DB_HOST=127.0.0.1" "ANTIPLAGIAT_DB_PORT=5432" "ANTIPLAGIAT_DB_NAME=antiplagiat" "ANTIPLAGIAT_DB_USER=antiplagiat_app" "ANTIPLAGIAT_DB_PASSWORD=<parol>" "ANTIPLAGIAT_PUBLIC_ORIGIN=http://127.0.0.1:3000"
nssm set AntiplagiatBackend AppStdout "D:\antiplagiat\logs\backend.log"
nssm set AntiplagiatBackend AppStderr "D:\antiplagiat\logs\backend.log"
nssm set AntiplagiatBackend AppRotateFiles 1
nssm set AntiplagiatBackend AppRotateBytes 10485760
nssm start AntiplagiatBackend
```

Frontend uchun xuddi shunday, `npm.cmd` va `run start -- --hostname 127.0.0.1 --port 3000` argumentlari bilan, alohida xizmat nomi ostida. Ikkisi ham `--host`/`--hostname 127.0.0.1` bilan qoladi — tashqi tarmoqqa ochilish arxitektura bo'yicha nazarda tutilmagan (`backend/auth.py`dagi `guard()`, `frontend/lib/proxy.ts`); tashqi kirish kerak bo'lsa, buni TLS bilan tugaydigan alohida reverse-proxy (masalan IIS yoki nginx) qiladi, ikki ilova jarayonining o'zi emas.

---

*Qarorlarning asosi (nega 12 belgi, nega 12 oy, nega bu defaultlar xavfsiz) uchun [docs/decisions.md](decisions.md) §13-dan boshlab qarang.*
