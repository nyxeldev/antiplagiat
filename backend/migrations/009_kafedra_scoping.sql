-- Kafedra skoplash -- roles-phase1ning 2-bosqichi (docs/decisions.md Sect.18/19).
-- Migratsiya 008 faqat kafedra JADVALI va users.kafedra_id ni qo'shgan edi,
-- ko'rinish cheklovisiz. Bu migratsiya korpus hujjatlarining o'ziga
-- kafedra bog'lanishini qo'shadi -- kafedra_mudiri endi faqat o'z
-- kafedrasiga (yoki kafedrasiz, "umumiy") tegishli hujjatlarni ko'radi.
--
-- Mavjud hujjatlar uchun BACKFILL YO'Q -- barchasi NULL ("umumiy") holicha
-- qoladi: eski yozuvlarda hujjat qaysi kafedraga tegishli ekani aniq
-- belgilanmagan (yuklovchi o'sha vaqtda kafedraga umuman biriktirilmagan
-- bo'lishi mumkin edi), shuning uchun taxminiy xaritalash emas, "umumiy"
-- yagona xavfsiz standart.
ALTER TABLE antiplagiat.corpus_documents
    ADD COLUMN kafedra_id uuid REFERENCES antiplagiat.kafedra(id);

-- kafedra_mudiri uchun har bir ro'yxatlash/moderatsiya so'rovi shu ustun
-- bo'yicha filtrlaydi (backend/corpus.py'dagi manager_scope()).
CREATE INDEX corpus_documents_kafedra ON antiplagiat.corpus_documents(kafedra_id);
