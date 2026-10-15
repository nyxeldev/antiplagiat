# Retrieval/matching sifatini o'lchash — v1

Versiya 1 · 2026-10-15 · Harness: [scripts/eval_retrieval.py](../../scripts/eval_retrieval.py) · Nazorat to'plami: [benchmarks/corpus-v1/](../../benchmarks/corpus-v1/)

**MAJBURIY OGOHLANTIRISH.** Bu raqamlar **sintetik, 18 hujjatli nazorat to'plamidan** olingan; haqiqiy BMI matnlaridagi sifatning isboti emas. O'xshashlik foizi plagiatning avtomatik isboti emas. FTS reytingi (`ts_rank`) hech qayerda foiz yoki o'xshashlik ko'rsatkichi sifatida ko'rsatilmaydi — u faqat nomzod saralash vositasi. Natijalar faqat shu kichik, qo'lda tuzilgan to'plamga tegishli; kattaroq yoki boshqacha tarkibli korpusda raqamlar boshqacha chiqishi tabiiy.

## 1. Konfiguratsiya

| Parametr | Qiymat |
| --- | --- |
| FTS konfiguratsiyasi | `simple` (PostgreSQL 18) |
| Baseline chunk oynasi / ustma-ustlik | 40 / 20 token |
| Baseline tsquery operatori | `OR` (ishlab chiqarishdagi amaldagi xulq) |
| Baseline nomzod limiti N | 5 |
| Nazorat to'plami hujjatlari | 18 ta korpus hujjati + 21 ta tekshiriluvchi so'rov |
| Tillar | o'zbek lotin (asosiy), rus, ingliz |
| Baza | **Faqat o'zi yaratgan, bir martalik disposable PostgreSQL klaster** (`backend.tests.postgres_fixture.isolated_postgres()`); haqiqiy `antiplagiat` bazasiga umuman ulanilmagan |
| Algoritm | Mavjud, o'zgartirilmagan `backend.comparison.matching.compare()` (exact + 5-token shingle) |

## 2. Nazorat to'plami tarkibi

**Korpus — 18 hujjat, 6 mavzu × 3 til** (tarix, biologiya, iqtisodiyot, adabiyot, ekologiya, pedagogika; har biri ~76–109 token).

**So'rovlar — 21 hujjat, 7 kategoriya** (har birida 3 ta namuna, morfologik faqat o'zbekcha):

| Kategoriya | Soni | Tillar | Ta'rifi |
| --- | --- | --- | --- |
| `verbatim` | 3 | uz/ru/en | Korpus hujjatining to'liq so'zma-so'z nusxasi |
| `partial` | 3 | uz/ru/en | Korpus hujjatining ~47–60% prefiksi + mustaqil davom |
| `paraphrase` | 3 | uz/ru/en | So'z tartibi o'zgargan, sinonim almashtirilgan, **5-token ketma-ketlik yo'q** |
| `morphological` | 3 | faqat uz | O'zbek agglutinativ qo'shimchalari o'zgartirilgan, o'zak saqlangan |
| `quoted` | 3 | uz/ru/en | Bitta aniq iqtibos (10–15 token), qolgan matn original va iqtibos atrofida |
| `hard_negative` | 3 | uz/ru/en | Bir xil mavzu, mustaqil yozilgan matn — hech narsa mos kelmasligi kerak |
| `unrelated` | 3 | uz/ru/en | Mutlaqo aloqasiz matn |

Ground truth [manifest.json](../../benchmarks/corpus-v1/manifest.json)da: har so'rov uchun `expected_sources` (retrieval uchun) va `match_text` (matching uchun, aniq quyi-qator yoki butun hujjat belgisi `"__FULL_TEXT__"`). Manifest mavjud `tokenize()`/`compare()` bilan bevosita tekshirilgan (3-bo'limga qarang).

## 3. A) Retrieval darajasi — asosiy raqamlar (baseline)

| Metrika | Qiymat | n (hisoblangan so'rovlar) |
| --- | --- | --- |
| Recall@1 | **1.00** | 15 / 15 (ijobiy kategoriyalar) |
| Recall@5 | **1.00** | 15 / 15 |
| Recall@10 | **1.00** | 15 / 15 |
| Precision@5 | 0.143 | 21 / 21 (manfiylarni ham qamraydi) |
| MRR | **1.00** | 15 / 15 |
| O'rtacha retrieval vaqti | 58 ms/so'rov | — |

`n=15` — faqat `expected_sources` bo'sh bo'lmagan so'rovlar (`verbatim`+`partial`+`paraphrase`+`morphological`+`quoted` = 5×3). Recall/MRR manfiy kategoriyalar (`hard_negative`, `unrelated`) uchun mazmunan aniqlanmagan, shuning uchun o'rtachaga kiritilmaydi (`backend/benchmark/metrics.py`dagi qoida). Precision@5 esa barcha 21 so'rov uchun hisoblangan — manfiy so'rovlarda ham retrieval nima qaytarishini ko'rsatish uchun ataylab aniqlangan.

**Xulosa:** 18 hujjatli korpusda FTS retrieval **barcha** ijobiy kategoriyalarda (parafraz va morfologik o'zgarishlar bilan birga!) to'g'ri manba hujjatni birinchi o'ringa chiqargan. Bu kutilgan — `simple` FTS so'z mavjudligiga asoslanadi (tartib/forma emas), shuning uchun parafraz va morfologik variant ham baribir ko'pgina asl so'zlarni saqlab qoladi.

## 4. B) Moslik darajasi — asosiy raqamlar (baseline)

| Metrika | Qiymat | n |
| --- | --- | --- |
| Precision | 1.00 | 15 / 21 (faqat kamida bitta token bashorat qilingan so'rovlar) |
| Recall | **0.714** | 21 / 21 |
| F1 | **0.714** | 21 / 21 |
| Yolg'on musbat bergan so'rovlar | **0** | 21 / 21 |

**Kategoriya bo'yicha (baseline, token darajasida, aniq):**

| Kategoriya | Retrieval recall@1 | Matching precision | Matching recall | Matching F1 |
| --- | --- | --- | --- | --- |
| `verbatim` | 1.00 | 1.00 | 1.00 | 1.00 |
| `partial` | 1.00 | 1.00 | 1.00 | 1.00 |
| `paraphrase` | 1.00 | — (hech narsa bashorat qilinmagan) | **0.00** | **0.00** |
| `morphological` | 1.00 | — (hech narsa bashorat qilinmagan) | **0.00** | **0.00** |
| `quoted` | 1.00 | 1.00 | 1.00 | 1.00 |
| `hard_negative` | — (kutilmagan) | 1.00 (yolg'on musbat yo'q) | 1.00 | 1.00 |
| `unrelated` | — (kutilmagan) | 1.00 (yolg'on musbat yo'q) | 1.00 | 1.00 |

**Bu qatordagi eng muhim xulosa:** `paraphrase` va `morphological` uchun retrieval **mukammal** (to'g'ri manbani topadi), lekin matching **0.00 recall** — ya'ni tizim nomzodni to'g'ri taklif qiladi, ammo odam o'qiganda "bu olingan matn" deb hisoblagan butun parchani **hech qachon** moslik sifatida belgilamaydi. Bu ikki daraja (nomzod tanlash va matndagi parcha aniqlash) orasidagi **qasddan qilingan ajratishning** aynan sababi va dalili: retrieval ishlaydi, lekin leksik moslovchi o'zgartirilgan so'z shakllarini "bir xil token" deb hisoblamaydi (stemming yo'q).

`hard_negative`/`unrelated` uchun F1=1.0 — bu "aniqlandi" degani emas, balki "to'g'ri hech narsa topilmadi, yolg'on musbat yo'q" degani (`false_positive_queries=0`, barcha 6 salbiy so'rovda).

## 5. Ablatsiya natijalari

### 5.1 tsquery: `OR` (baseline) vs `AND`

| Metrika (umumiy) | `OR` (baseline) | `AND` |
| --- | --- | --- |
| Recall@1 | **1.00** | **0.20** |
| Recall@5 | **1.00** | **0.20** |
| MRR | **1.00** | **0.20** |
| Precision@5 | 0.143 (n=21) | 1.00 (n=**faqat 3**!) |
| O'rtacha retrieval vaqti | 58 ms | 44 ms |

Kategoriya bo'yicha `AND` ostida recall@1: `verbatim`=0.67, `partial`=0.33, `paraphrase`=**0.00**, `morphological`=**0.00**, `quoted`=**0.00**.

**Xulosa: `AND` retrieval'ni amalda ishdan chiqaradi.** `plainto_tsquery`ning tabiiy `AND` semantikasi 40 tokenlik so'rov oynasidagi **barcha** so'zlarning bitta chunkda birga uchrashini talab qiladi — bu talab hatto to'liq nusxalarning uchdan bir qismida ham bajarilmaydi (chunk chegaralari so'rov oynasi bilan mos kelmagani uchun), parafraz/morfologik/iqtibos holatlarida esa umuman bajarilmaydi. `precision_at_5_n=3` buni tasdiqlaydi: 21 so'rovdan atigi 3 tasi umuman biror nomzod qaytargan. Bu amaldagi `OR` tanlovini (production kodida, `backend/corpus.py`dagi izohda ham yozilgan) to'g'ridan-to'g'ri oqlaydi.

### 5.2 Chunk oynasi: 40/20 (baseline) vs 80/40

| Metrika (umumiy) | 40/20 (baseline) | 80/40 |
| --- | --- | --- |
| Recall@1 / @5 / MRR | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| Matching P / R / F1 | 1.00 / 0.714 / 0.714 | 1.00 / 0.714 / 0.714 |

**Bu to'plamda farq aniqlanmadi** — ikkala konfiguratsiyada ham aynan bir xil natija. Sabab o'lchandi: korpus hujjatlari qisqa (76–109 token), shuning uchun 80/40 oynasida ko'pchilik hujjat atigi **1–2 chunk**ka tushadi (40/20da esa 3–5 ta), ammo bu kichik hujjat uchun baribir deyarli butun lug'atni bitta chunkka sig'diradi va FTS natijasiga ta'sir qilmaydi. **Bu natijani "chunk o'lchami ahamiyatsiz" deb umumlashtirish noto'g'ri bo'lar edi** — bu faqat shu qisqa-hujjatli nazorat to'plamining chegarasi; uzunroq, ko'p bo'limli haqiqiy hujjatlarda farq chiqishi mumkin (7-bo'limda qayd etilgan).

### 5.3 Nomzod limiti N: 5 (baseline) vs 20

| Metrika (umumiy) | N=5 (baseline) | N=20 |
| --- | --- | --- |
| Recall@1 / @5 / MRR | 1.00 / 1.00 / 1.00 | 1.00 / 1.00 / 1.00 |
| Matching P / R / F1 | 1.00 / 0.714 / 0.714 | 1.00 / 0.714 / 0.714 |

**Farq yo'q** — kutilgan, chunki N=5'ning o'zida recall@5 allaqachon 1.00 (mukammal). 18 hujjatli kichik korpusda N ning kattalashishi hech narsani yaxshilamaydi, chunki yaxshilash uchun joy yo'q. Kattaroq, ko'proq "shovqin" beruvchi korpusda N=20 farq berishi mumkin — bu to'plam bunga javob bera olmaydi (7-bo'limda qayd etilgan).

## 6. Xom natijalar

- To'liq jadval (4 konfiguratsiya × 21 so'rov = 84 qator, har biri uchun aniq `ranked_ids`, token sonlari, vaqt): [benchmarks/corpus-v1/results/raw.csv](../../benchmarks/corpus-v1/results/raw.csv)
- Hisoblangan yig'indilar (umumiy + har kategoriya, har konfiguratsiya uchun): [benchmarks/corpus-v1/results/summary.json](../../benchmarks/corpus-v1/results/summary.json)

## 7. Tekshirilgan determinizm

`scripts/eval_retrieval.py --repeat 2` ikki **mustaqil** bir martalik disposable PostgreSQL klasterida to'liq ishga tushirildi. Natija: **vaqt ustunlaridan (`retrieval_seconds`/`matching_seconds`) tashqari barcha 84×16 qiymat ikkala yurishda aynan bir xil** edi (retrieval/matching metrikalari, `ranked_ids` tartibi, token sonlari — barchasi). Hujjat idlari `uuid5(FIXED_NAMESPACE, manifest_id)` bilan deterministik hosil qilinadi, shuning uchun `candidates()`dagi SQL tartiblash zanjiridagi oxirgi tie-break ham barqaror.

## 8. Cheklovlar va keyingi qadamlar

- **18 hujjatli korpus juda kichik.** Barcha ijobiy kategoriyalarda recall@1=1.0 bo'lishi qisman shu bilan izohlanadi — "shovqin" beruvchi, mavzudosh-lekin-aloqasiz hujjatlar soni kam. Kattaroq (50–200+) korpusda retrieval ancha qiyinlashishi kutiladi.
- **Chunk va N ablatsiyalari bu to'plamda farq ko'rsatmadi** — yuqorida izohlangani kabi, bu to'plamning cheklovi, konfiguratsiya ahamiyatsizligining isboti emas.
- **Faqat bitta algoritm versiyasi (`lexical-shingle-v1`) va bitta normalizatsiya (`uz-latin-v2`) sinaldi.**
- **O'zbek kirill va arab yozuvlari bu bosqichda yo'q** — `docs/roadmap.md`da qayd etilgan kelajak ishi.
- **DOCX/PDF formatidagi benchmark hujjatlari yo'q** — barcha fayllar TXT.
- Natijalar faqat shu kod versiyasiga tegishli; keyingi algoritmik o'zgarishlardan keyin qayta yurgizish tavsiya etiladi.

## 9. Takrorlash

```powershell
Set-Location D:\antiplagiat
.\.venv\Scripts\python.exe scripts\eval_retrieval.py
.\.venv\Scripts\python.exe scripts\eval_retrieval.py --repeat 2   # determinizmni tekshirish
```

Harness o'zi bir martalik disposable PostgreSQL klaster yaratadi (`initdb`/`pg_ctl` talab qiladi) va oxirida avtomatik tozalaydi; haqiqiy `antiplagiat` bazasiga hech qanday holatda ulanmaydi.
