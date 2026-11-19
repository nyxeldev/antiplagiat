-- FAZA "roles-phase1": kafedra qamrovi va yangi besh rolli modelning
-- poydevori. Kafedra bo'yicha CHEKLASH bu migratsiyada YO'Q -- faqat jadval
-- va ustun qo'shiladi (docs/decisions.md Sect.18). Scoping 2-fazada.
--
-- Rol ko'chirish (eski -> yangi), ANIQ va QAYTARILADIGAN -- har bir qatorning
-- oldingi role/can_submit_to_corpus qiymati quyidagi CASE orqali bitta,
-- deterministik yangi rolga tushadi:
--   user  + can_submit_to_corpus=true  -> ustoz
--   user  + can_submit_to_corpus=false -> talaba
--   reviewer                           -> ustoz   (amalda hech qachon ishlatilmagan rol)
--   corpus_manager                     -> kafedra_mudiri
--   admin                              -> admin (o'zgarmaydi)
-- super_admin hech kimga bu migratsiyada berilmaydi -- faqat CLI orqali
-- qo'lda tayinlanadi (backend/manage.py "assign-role").
--
-- Eski CHECK avval OLIB TASHLANADI, chunki quyidagi UPDATE o'zi vaqtincha
-- ESKI to'plamga mos kelmaydigan qiymat ('ustoz' kabi) yozadi -- eski
-- cheklov o'rnida qolsa, aynan shu UPDATE'ning o'zi rad etilardi. Yangi,
-- torroq cheklov faqat MA'LUMOT allaqachon ko'chirilgandan KEYIN qo'shiladi.
ALTER TABLE antiplagiat.users DROP CONSTRAINT users_role_check;

UPDATE antiplagiat.users SET role = CASE
    WHEN role = 'user' AND can_submit_to_corpus THEN 'ustoz'
    WHEN role = 'user' THEN 'talaba'
    WHEN role = 'reviewer' THEN 'ustoz'
    WHEN role = 'corpus_manager' THEN 'kafedra_mudiri'
    ELSE role
END;

ALTER TABLE antiplagiat.users ADD CONSTRAINT users_role_check
    CHECK (role IN ('talaba', 'ustoz', 'kafedra_mudiri', 'admin', 'super_admin'));
-- The column default was still the now-invalid 'user' -- any future INSERT
-- relying on it (none in application code today; create_user() always
-- passes role explicitly) would otherwise violate the CHECK above.
ALTER TABLE antiplagiat.users ALTER COLUMN role SET DEFAULT 'talaba';

-- can_submit_to_corpus ustuni ATAYLAB o'chirilmadi (topshiriq shartiga ko'ra)
-- -- u endi backend/auth.py'da "ustoz" roli ustiga QO'SHIMCHA, admin
-- bekor qila oladigan kalit sifatida ishlatiladi (bitta ustozning taklif
-- huquqini rolni o'zgartirmasdan vaqtincha to'xtatish imkoni). Bu migratsiya
-- uni ustozga aylangan HAR BIR qatorda avvalgi qiymatida qoldiradi -- shu
-- sababli yuqoridagi UPDATE uni o'zgartirmaydi.

CREATE TABLE antiplagiat.kafedra (
    id uuid PRIMARY KEY,
    nomi text NOT NULL CHECK (btrim(nomi) <> '' AND char_length(nomi) <= 300),
    qisqa_kodi text UNIQUE NOT NULL CHECK (btrim(qisqa_kodi) <> '' AND char_length(qisqa_kodi) <= 32),
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Nullable har bir rol uchun: kafedralar ro'yxati hali bo'sh (CLI orqali
-- keyinroq to'ldiriladi), shuning uchun mavjud HECH BIR akkaunt (roli qanday
-- bo'lishidan qat'i nazar) bu migratsiyada kafedraga biriktirilmaydi. admin/
-- super_admin kafedrasiz QOLISHI ham me'yor (ular kafedra darajasida emas,
-- butun tizim darajasida ishlaydi) -- lekin bu ustunning o'zi har qanday rol
-- uchun ham NULL bo'lishiga yo'l qo'yadi, chunki qamrov hali majburiy emas.
ALTER TABLE antiplagiat.users
    ADD COLUMN kafedra_id uuid REFERENCES antiplagiat.kafedra(id);
