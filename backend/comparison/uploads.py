"""Bound multipart bytes while streaming, before extraction or unbounded buffering."""
import logging
import unicodedata
from pathlib import Path

from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header

from .policy import ComparisonError, MAX_BODY_BYTES, MAX_FILE_BYTES, MAX_TOTAL_BYTES

logging.getLogger("python_multipart.multipart").disabled = True


class Uploads:
    def __init__(self, folder, content_type):
        mime, options = parse_options_header(content_type)
        boundary = options.get(b"boundary", b"")
        if mime != b"multipart/form-data" or not 1 <= len(boundary) <= 200:
            raise ComparisonError("upload_format", "multipart/form-data yuklash formati kerak.", 400)
        self.folder, self.items, self.stream = folder, [], None
        self.body_size, self.total, self.finished = 0, 0, False
        callbacks = {"on_" + name: getattr(self, name) for name in (
            "part_begin", "header_field", "header_value", "header_end", "headers_finished",
            "part_data", "part_end", "end")}
        self.parser = MultipartParser(boundary, callbacks)

    def part_begin(self):
        if len(self.items) >= 6:
            raise ComparisonError("file_count", "Bitta hujjat va ko‘pi bilan 5 ta manba kerak.", 400)
        self.headers, self.field, self.value = {}, bytearray(), bytearray()
        self.header_size, self.file_size = 0, 0

    def header_field(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            raise ComparisonError("headers_limit", "Fayl sarlavhasi juda uzun.", 400)
        self.field.extend(data[start:end])

    def header_value(self, data, start, end):
        self.header_size += end - start
        if self.header_size > 8192:
            raise ComparisonError("headers_limit", "Fayl sarlavhasi juda uzun.", 400)
        self.value.extend(data[start:end])

    def header_end(self):
        field = bytes(self.field).lower()
        if field in self.headers:
            raise ComparisonError("upload_format", "Takrorlangan fayl sarlavhasi.", 400)
        self.headers[field] = bytes(self.value)
        self.field.clear()
        self.value.clear()

    def headers_finished(self):
        disposition, options = parse_options_header(self.headers.get(b"content-disposition", b""))
        role = options.get(b"name")
        if disposition != b"form-data" or role not in (b"document", b"sources") or b"filename" not in options:
            raise ComparisonError("upload_format", "document va sources fayl maydonlari kerak.", 400)
        raw = options[b"filename"].decode("utf-8", errors="replace")
        name = raw.replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(c for c in name if not unicodedata.category(c).startswith("C"))
        if not name or len(name) > 200:
            raise ComparisonError("filename", "Fayl nomi bo‘sh yoki juda uzun.", 400)
        if Path(name).suffix.lower() not in (".txt", ".pdf", ".docx"):
            raise ComparisonError("unsupported", "Faqat TXT, DOCX va PDF qabul qilinadi.", 415, name)
        item = {"role": role.decode(), "name": name, "path": f"upload-{len(self.items)}"}
        self.items.append(item)
        self.stream = (self.folder / item["path"]).open("xb")

    def part_data(self, data, start, end):
        size = end - start
        self.total += size
        self.file_size += size
        if self.file_size > MAX_FILE_BYTES:
            raise ComparisonError("file_limit", "Bitta fayl 10 MiB dan oshmasligi kerak.", 413)
        if self.total > MAX_TOTAL_BYTES:
            raise ComparisonError("total_limit", "Fayllarning jami hajmi 30 MiB dan oshmasligi kerak.", 413)
        if self.stream is None:
            raise ComparisonError("upload_format", "Fayl sarlavhasi yetishmaydi.", 400)
        self.stream.write(data[start:end])

    def part_end(self):
        self.close()

    def end(self):
        self.finished = True

    def write(self, data):
        self.body_size += len(data)
        if self.body_size > MAX_BODY_BYTES:
            raise ComparisonError("total_limit", "Yuklash hajmi chegaradan oshdi.", 413)
        self.parser.write(data)

    def finish(self):
        self.parser.finalize()
        if not self.finished or self.stream is not None:
            raise ComparisonError("incomplete_upload", "Fayl yuklash to‘liq tugamadi.", 400)
        documents = [item for item in self.items if item["role"] == "document"]
        sources = [item for item in self.items if item["role"] == "sources"]
        # Whether at least one source is required (manual or corpus) is a
        # request-level policy, not a parsing concern -- the caller (which
        # knows include_corpus) checks that. Here we only bound the count.
        if len(documents) != 1 or len(sources) > 5:
            raise ComparisonError("file_count", "Bitta tekshiriladigan hujjat va ko‘pi bilan 5 ta manba kerak.", 400)
        return documents + sources

    def close(self):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
