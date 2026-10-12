# Antiplagiat frontend

Next.js App Router va TypeScript asosidagi minimal o‘zbekcha bosh sahifa.
Oddiy CSS va tizim shriftlari ishlatiladi. Bitta hujjat va 1–5 manba yuklanib,
lokal FastAPI orqali leksik hisobot olinadi. Autentifikatsiya yo‘q.

Avval boshqa PowerShell oynasida backendni ishga tushiring:

```powershell
Set-Location D:\aniplagiat
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Brauzer `/api/compare` ga murojaat qiladi. Serverdagi `ANTIPLAGIAT_API_URL`
standart qiymati `http://127.0.0.1:8000`; faqat lokal HTTP manzil qabul qilinadi.
DB sozlamalari frontendga kerak emas. Fayllar doimiy saqlanmaydi.

Buyruqlar Windows PowerShell 5.1 uchun:

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run dev -- --hostname 127.0.0.1 --port 3000
```

3000-port bo‘sh bo‘lishi kerak. Serverni shu oynada `Ctrl+C` bilan to‘xtating.

```powershell
Set-Location D:\aniplagiat\frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd run start -- --hostname 127.0.0.1 --port 3000
```

Yangi checkout uchun `npm.cmd ci` ishlating; `package-lock.json` saqlanadi.
Paket versiyalari, bo‘sh port tanlash, HTTP tekshiruvi va ma’lum dependency
cheklovlari [loyiha README’sida](../README.md#frontendni-ishga-tushirish-va-tekshirish).
