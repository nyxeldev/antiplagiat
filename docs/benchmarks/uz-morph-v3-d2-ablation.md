# uz-latin-v3 — D2: `MIN_WORD_LEN_TO_STRIP` ablatsiyasi (7 / 6 / 5)

Versiya 1 · 2026-10-18 · Oldingi hisobot: [uz-morph-v3-d1-fixes.md](uz-morph-v3-d1-fixes.md) · Xom ma'lumot: [uz-morph-v3-d2-ablation.csv](uz-morph-v3-d2-ablation.csv)

**Faqat o'lchov va tavsiya. `backend/comparison/uz_latin_v3.py`dagi `MIN_WORD_LEN_TO_STRIP = 7` qiymati O'ZGARTIRILMADI.** Pastdagi uchta qiymat runtime monkeypatch orqali (bitta jarayon ichida, fayl tahrirlanmasdan) o'lchandi — skript tugagach, committed kod avvalgidek 7'da qoladi.

## Natijalar

| `MIN_WORD_LEN_TO_STRIP` | Stemlangan o'zbekcha tokenlar | Retrieval (barcha qatlamlar) | **Yolg'on musbat (hard_negative+unrelated, n=14)** | en/ru noto'g'ri qirqilgan so'zlar |
| --- | --- | --- | --- | --- |
| **7 (hozirgi)** | 3356/11695 (28.7%) | recall@1=0.7170, @5/@10=0.8491, MRR=0.7575 | **0** | 11 |
| 6 | 3703/11695 (31.7%) | **AYNAN bir xil** | **0** | 13 (+2: `similar`→`simi`, `popular`→`popu`) |
| 5 | 3915/11695 (33.5%) | **AYNAN bir xil** | **0** | 14 (+1 yana) |

Qatlamlar bo'yicha batafsil (uchta qiymat uchun AYNAN bir xil raqamlar, shuning uchun bitta qator sifatida):

| Qatlam | n | recall@1 | recall@5 | recall@10 | MRR |
| --- | --- | --- | --- | --- | --- |
| morfologik, hammasi | 15 | 0.8667 | 1.0000 | 1.0000 | 0.9022 |
| morfologik YUQORI (≥35%) | 5 | 0.6000 | 1.0000 | 1.0000 | 0.7067 |
| morfologik PAST (<20%) | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| paraphrase | 15 | 0.6000 | 0.7333 | 0.7333 | 0.6389 |
| BARCHASI | 67 | 0.7170 | 0.8491 | 0.8491 | 0.7575 |

## Tahlil

**7dan 6ga, 6dan 5ga tushirish retrieval darajasida BIR TOMCHI HAM farq bermadi** — barcha besh qatlamda, barcha to'rt metrikada (recall@1/5/10, MRR) uchta qiymat ham bit-baytiga bir xil raqam berdi. Buning sababi oddiy: corpus-v2'dagi morfologik/paraphrase so'rovlarning HAL QILUVCHI suffiks farqlari allaqachon ≥7 belgili so'zlarda joylashgan (masalan "kelmoqda"/"kelgan", "qilinmoqda" kabi) — bu benchmark uchun 7 dan past chegarada YANGI qamrov olingan so'zlar aynan RETRIEVAL natijasini hal qiladigan so'zlar DOIRASIGA kirmaydi.

Shu bilan birga, **noto'g'ri qirqilgan chet so'zlar soni MONOTON OSHDI**: 11→13→14. Yangi xato misollar: `similar`→`simi`, `popular`→`popu` (ikkisi ham 7 belgi, aynan 6'ga tushirilganda birinchi marta qamrovga kiradi). Bu — FOYDASIZ xavf: hech qanday o'lchanadigan retrieval foydasi yo'q, faqat lug'atsiz himoyaning teshigi kattalashadi.

**Yolg'on musbat (matching darajasida, hard_negative+unrelated)** uchta qiymatda ham 0 — lekin bu natijani "xavfsiz" deb talqin qilmaslik kerak: bu faqat USHBU 14 so'rov uchun compare() natijasida mos kelish paydo bo'lmagani degani (chunki C4'da ko'rsatilganidek, matching hamon v2 tokenlarida ishlaydi — retrieval'dagi o'zgarish FAQAT qaysi hujjatlar nomzod bo'lib tanlanishiga ta'sir qiladi, compare()ning o'ziga emas). Kattaroq yoki boshqacha tarkibli to'plamda chegarani pasaytirish boshqa natija berishi mumkin — bu raqam faqat USHBU sintetik to'plamga tegishli.

## Tavsiya

**7da qoldirish — eng yaxshi muvozanat.** Asoslash: 6 va 5 ushbu to'plamda **noldan katta foyda bermaydi** (retrieval raqamlari aynan bir xil), lekin **aniq va o'suvchi narxga ega** (noto'g'ri qirqilgan chet so'zlar soni monoton oshadi). Foyda-narx nisbati 7dan pastga tushishni hech qanday raqam bilan oqlamaydi — bu "ehtiyotkor, asossiz tanlangan raqam" emas, balki o'lchov tasdiqlagan to'g'ri tanlov bo'lib chiqdi.

Chegara o'zgartirilmadi, tavsiya shu — TO'XTALDI.
