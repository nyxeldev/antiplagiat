-- Profil sahifasini kengaytirish -- roles-phase1 (docs/decisions.md Sect.25):
-- har bir rol o'z-o'zidan to'liq ism qo'yishi, profil rasmi yuklashi va
-- login (username) o'zgartirishi mumkin bo'ladi.
--
-- Rasm DOIMIY fayl tizimida emas, shu jadvalning o'zida (bytea) saqlanadi --
-- korpus hujjatlari ham hech qachon xom baytlarni diskda saqlamaydi (faqat
-- vaqtinchalik tempdir, backend/corpus_api.py), shu konventsiyaga mos.
-- Pillow kabi rasm kutubxonasi ATAYLAB qo'shilmagan -- qayta kodlash/resize
-- qilinmaydi, faqat magic-byte tekshiruvi (backend/auth.py) + qattiq hajm
-- chegarasi bilan kifoyalanadi.
ALTER TABLE antiplagiat.users ADD COLUMN full_name text
    CHECK (full_name IS NULL OR char_length(full_name) BETWEEN 1 AND 120);
ALTER TABLE antiplagiat.users ADD COLUMN avatar bytea;
ALTER TABLE antiplagiat.users ADD COLUMN avatar_mime text
    CHECK (avatar_mime IS NULL OR avatar_mime IN ('image/png', 'image/jpeg', 'image/webp'));
