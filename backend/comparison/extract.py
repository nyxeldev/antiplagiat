"""Extract text only; never execute document code or resolve external resources."""
import re
import zipfile
from pathlib import Path

from defusedxml import ElementTree
from pypdf import PdfReader
from pypdf.errors import DependencyError

from .policy import (
    ComparisonError, MAX_FILE_BYTES, MAX_PAGES, MAX_TEXT_CHARS,
    MAX_XML_BYTES, MAX_ZIP_BYTES, MAX_ZIP_ENTRIES,
)

WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SKIP_WORD = {WORD + tag for tag in ("drawing", "pict", "object", "txbxContent", "del")}


def paragraphs(element):
    if element.tag in SKIP_WORD:
        return
    if element.tag == WORD + "p":
        yield element
        return
    for child in element:
        yield from paragraphs(child)


def paragraph_text(element):
    if element.tag in SKIP_WORD:
        return
    if element.tag == WORD + "t":
        yield element.text or ""
    elif element.tag in (WORD + "br", WORD + "cr"):
        yield "\n"
    elif element.tag == WORD + "tab":
        yield "\t"
    else:
        for child in element:
            if child.tag != WORD + "p":
                yield from paragraph_text(child)


def assemble(parts, kind):
    text, segments, size = [], [], 0
    for number, part in enumerate(parts, 1):
        if size + len(part) > MAX_TEXT_CHARS:
            raise ComparisonError("text_limit", "Ajratilgan matn 200 000 belgidan oshdi.")
        segments.append({"kind": kind, "number": number, "start": size, "end": size + len(part)})
        text.append(part)
        size += len(part) + 2
    return {"text": "\n\n".join(text), "segments": segments}


def docx_parts(path):
    with path.open("rb") as stream:
        if stream.read(8) == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
            raise ComparisonError("encrypted", "Shifrlangan yoki eski Word formati qo‘llanmaydi.")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES or sum(item.file_size for item in entries) > MAX_ZIP_BYTES:
            raise ComparisonError("archive_limit", "DOCX arxivi ochilganda 50 MiB yoki 1000 element chegarasidan oshadi.")
        if any(item.flag_bits & 1 for item in entries):
            raise ComparisonError("encrypted", "Shifrlangan DOCX qo‘llanmaydi.")
        names = [item.filename for item in entries]
        if len(names) != len(set(names)) or "[Content_Types].xml" not in names:
            raise ComparisonError("corrupt", "DOCX tuzilishi noto‘g‘ri.")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise ComparisonError("unsupported", "Makrosli Word fayli qo‘llanmaydi.")
        info = archive.getinfo("word/document.xml")
        if info.file_size > MAX_XML_BYTES:
            raise ComparisonError("archive_limit", "DOCX asosiy XML matni 8 MiB dan oshdi.")
        with archive.open(info) as stream:
            xml = stream.read(MAX_XML_BYTES + 1)
        if len(xml) > MAX_XML_BYTES:
            raise ComparisonError("archive_limit", "DOCX XML hajmi chegaradan oshdi.")
        root = ElementTree.fromstring(xml, forbid_dtd=True)
        body = root.find(WORD + "body")
        if root.tag != WORD + "document" or body is None:
            raise ComparisonError("unsupported", "Bu DOCX XML turi qo‘llanmaydi.")
        for paragraph in paragraphs(body):
            yield "".join(paragraph_text(paragraph))


def pdf_parts(path):
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ComparisonError("corrupt", "PDF sarlavhasi noto‘g‘ri.")
        try:
            reader = PdfReader(stream, strict=True)
        except DependencyError:
            # AES-encrypted PDFs can request a crypto extra while opening.
            raise ComparisonError("encrypted", "Shifrlangan PDF qo‘llanmaydi. Parolsiz nusxa kerak.") from None
        if reader.is_encrypted:
            raise ComparisonError("encrypted", "Shifrlangan PDF qo‘llanmaydi. Parolsiz nusxa kerak.")
        if len(reader.pages) > MAX_PAGES:
            raise ComparisonError("page_limit", "PDF 200 sahifadan oshmasligi kerak.")
        if not reader.pages:
            raise ComparisonError("empty", "PDFda sahifalar yo‘q.")
        for page in reader.pages:
            text = page.extract_text() or ""
            if not text.strip():
                raise ComparisonError("no_text_layer", "PDFda matnsiz sahifa bor: skan yoki bo‘sh sahifa. OCR mavjud emas.")
            yield text


def extract(path, name):
    path = Path(path)
    suffix = Path(name).suffix.lower()
    try:
        if suffix not in (".txt", ".docx", ".pdf"):
            raise ComparisonError("unsupported", "Faqat UTF-8 TXT, DOCX va matn qatlamli PDF qabul qilinadi.")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ComparisonError("file_limit", "Bitta fayl 10 MiB dan oshmasligi kerak.", 413)
        if not path.stat().st_size:
            raise ComparisonError("empty", "Fayl bo‘sh.")
        if suffix == ".txt":
            raw = path.read_bytes()
            if raw.startswith((b"%PDF-", b"PK\x03\x04", b"\xd0\xcf\x11\xe0")):
                raise ComparisonError("type_mismatch", "Fayl mazmuni TXT turiga mos emas.")
            text = raw.decode("utf-8-sig")
            if "\x00" in text or any(ord(c) < 32 and c not in "\r\n\t\f" for c in text):
                raise ComparisonError("invalid_text", "TXT faylda ikkilik yoki boshqaruv belgilar bor.")
            if len(text) > MAX_TEXT_CHARS:
                raise ComparisonError("text_limit", "Ajratilgan matn 200 000 belgidan oshdi.")
            segments = [{"kind": "paragraph", "number": i, "start": m.start(), "end": m.end()}
                        for i, m in enumerate(re.finditer(r"[^\r\n]+", text), 1)]
            result = {"text": text, "segments": segments}
        elif suffix == ".docx":
            result = assemble(docx_parts(path), "paragraph")
        else:
            result = assemble(pdf_parts(path), "page")
        if not result["text"].strip():
            raise ComparisonError("empty", "Fayldan o‘qiladigan matn topilmadi.")
        result.update(name=name, format=suffix[1:])
        return result
    except ComparisonError as error:
        error.file = name
        raise
    except UnicodeError:
        raise ComparisonError("encoding", "TXT fayl UTF-8 kodlashida bo‘lishi kerak.", file=name) from None
    except MemoryError:
        raise ComparisonError("resource_limit", "Parser xotira chegarasiga yetdi.", file=name) from None
    except Exception:
        raise ComparisonError("corrupt", "Fayl buzilgan yoki ushbu parser bilan o‘qib bo‘lmaydi.", file=name) from None
