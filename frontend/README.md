# Antiplagiat frontend

Next.js App Router va TypeScript asosidagi minimal o‘zbekcha bosh sahifa.
Oddiy CSS va tizim shriftlari ishlatiladi. Bitta hujjat va 1–5 manba yuklanib,
lokal FastAPI orqali leksik hisobot olinadi va PostgreSQL’da hisobga bog‘lanadi.
Login/logout, `/history` va `/reports/[id]` bor; yangi/saqlangan snapshot
bir xil highlight va ogohlantirishlar bilan ko‘rsatiladi.

Avval boshqa PowerShell oynasida backendni ishga tushiring:

```powershell
Set-Location D:\aniplagiat
.\scripts\start_backend.ps1
```

Brauzer `/api/compare` ga murojaat qiladi. Serverdagi `ANTIPLAGIAT_API_URL`
standart qiymati `http://127.0.0.1:8000`; faqat lokal HTTP manzil qabul qilinadi.
DB sozlamalari frontendga berilmaydi. Binar fayllar doimiy saqlanmaydi,
lekin ajratilgan matnlar maxfiy shaxsiy snapshot sifatida saqlanadi.
Migratsiya va CLI akkauntini avval loyiha README’sidagi tartibda yarating.
Frontend/backend `ANTIPLAGIAT_PUBLIC_ORIGIN` bir xil bo‘lsin;
standart `http://127.0.0.1:3000`. Cookie HttpOnly/SameSite=Strict,
HTTPS origin’da Secure. Token URL/localStorage’da saqlanmaydi.

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
