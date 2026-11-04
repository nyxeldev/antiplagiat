import io
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from starlette.requests import Request

from backend.comparison import api, extract as extraction, matching, runner, uploads
from backend.comparison.policy import ComparisonError, MAX_FILE_BYTES
from backend.tests.fixtures import TEXT, docx, pdf, multipart


def document(text, name="sample.txt"):
    return {"name": name, "format": "txt", "text": text,
            "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(text)}]}


class MatchingTests(unittest.TestCase):
    def test_identical_and_different(self):
        for other, expected in [(TEXT, 100), ("osmon dengiz toglar daraxtlar qushlar yomgir", 0)]:
            with self.subTest(expected=expected):
                result = matching.compare(document(TEXT), [document(other)])
                self.assertEqual(result["coverage_percent"], expected)
                if expected:
                    self.assertEqual(result["sources"][0]["matches"][0]["method"], "exact")

    def test_partial_duplicate_sources_and_occurrences(self):
        target = "bir ikki uch tort besh olti yetti sakkiz toqqiz on"
        source = "bir ikki uch tort besh olti"
        result = matching.compare(document(target), [document(source), document(source)])
        self.assertEqual(result["coverage_percent"], 60)
        self.assertEqual(result["matched_tokens"], 6)
        repeated = matching.compare(document(source + " boshqa " + source), [document(source)])
        self.assertEqual(repeated["matched_tokens"], 12)

    def test_overlapping_different_sources(self):
        result = matching.compare(document("a b c d e f g h i j"), [document("a b c d e f"), document("e f g h i j")])
        self.assertEqual(result["coverage_percent"], 100)
        self.assertEqual([s["coverage_percent"] for s in result["sources"]], [60, 60])

    def test_four_token_match_does_not_meet_threshold(self):
        result = matching.compare(document("a b c d unrelated"), [document("a b c d other")])
        self.assertEqual(result["matched_tokens"], 0)

    def test_unicode_apostrophes_whitespace_and_original_coordinates(self):
        left = "😀 Kirish. O‘ZBEK  gʻoya\nmaʼno cafe\u0301 ＡＢＣ Straße. Yakun."
        right = "o'zbek g'oya ma'no café abc strasse"
        result = matching.compare(document(left), [document(right)])
        match = result["sources"][0]["matches"][0]
        self.assertEqual(match["method"], "shingle")
        self.assertEqual(match["document"]["text"], "O‘ZBEK  gʻoya\nmaʼno cafe\u0301 ＡＢＣ Straße")
        for role, text in [("document", left), ("source", right)]:
            span = match[role]
            self.assertEqual(text[span["start"]:span["end"]], span["text"])
        self.assertEqual(match["document"]["start"], left.index("O‘ZBEK"))

    def test_short_empty_token_and_operation_limits(self):
        for text, code in [("😀 !!!", "empty"), ("bir ikki", "too_short")]:
            with self.subTest(code=code), self.assertRaises(ComparisonError) as raised:
                matching.tokenize(text)
            self.assertEqual(raised.exception.code, code)
        with patch.object(matching, "MAX_TOKENS", 5), self.assertRaises(ComparisonError):
            matching.tokenize(TEXT)
        with patch.object(matching, "MAX_OPERATIONS", 2), self.assertRaises(ComparisonError):
            matching.compare(document("a " * 20), [document("a " * 18)])

    def test_latin_internal_invisible_runs_and_original_highlights(self):
        clean = "lotin matn uchun aniq manba nusxa"
        for invisible in ("\u200b", "\u00ad", "\u200c", "\ufeff", "\u200b\u00ad\u200c\ufeff\u200b"):
            changed = clean.replace("lotin", "lo" + invisible + "tin")
            for target, source in [(changed, clean), (clean, changed)]:
                with self.subTest(invisible=repr(invisible), target=target):
                    result = matching.compare(document(target), [document(source)])
                    self.assertEqual(result["coverage_percent"], 100)
                    self.assertEqual(result["token_count"], 6)
                    self.assertEqual(result["document"]["text"], target)
                    self.assertEqual(result["sources"][0]["text"], source)
                    self.assertIn(matching.INVISIBLE_WARNING, result["limitations"])
                    self.assertEqual(result["parameters"]["normalization_version"], "uz-latin-v2")
                    match = result["sources"][0]["matches"][0]
                    self.assertEqual(match["method"], "shingle")
                    for role, original in [("document", target), ("source", source)]:
                        self.assertEqual(match[role]["start"], 0)
                        self.assertEqual(match[role]["end"], len(original))
                        self.assertEqual(match[role]["text"], original)
            # Equal original slices can still be called exact, even with controls.
            identical = matching.compare(document(changed), [document(changed)])
            self.assertEqual(identical["sources"][0]["matches"][0]["method"], "exact")
        exact = matching.compare(document(clean), [document(clean)])
        self.assertNotIn(matching.INVISIBLE_WARNING, exact["limitations"])

    def test_invisible_boundaries_and_other_scripts_are_retained(self):
        clean = "lotin matn uchun aniq manba nusxa"
        for control in ("\u200b", "\u00ad", "\u200c", "\ufeff", "\u200b\u200c"):
            for text in (control + clean + control,
                         clean.replace(" ", " " + control + " "),
                         clean.replace(" ", "," + control)):
                with self.subTest(text=repr(text)):
                    self.assertEqual(matching.ignored_invisibles(text), set())
                    tokens = matching.tokenize(text)
                    for token in tokens:
                        self.assertEqual(text[token["start"]:token["end"]], token["value"])
                    self.assertNotIn(matching.INVISIBLE_WARNING,
                                     matching.compare(document(text), [document(clean)])["limitations"])
            for other in ("ع" + control + "ب", "क" + control + "ष",
                          "а" + control + "б", "a" + control + "ب"):
                self.assertEqual(matching.ignored_invisibles(other), set())
                text = other + " " + clean
                result = matching.compare(document(text), [document(text)])
                self.assertEqual(result["document"]["text"], text)
                self.assertNotIn(matching.INVISIBLE_WARNING, result["limitations"])
        # Unlisted Cf and combining Mn characters are not globally removed.
        self.assertEqual(matching.ignored_invisibles("a\u200db a\u2060b a\u0301b"), set())
        self.assertEqual([t["value"] for t in matching.tokenize("café cafe\u0301 o‘zbek gʻoya maʼno")],
                         ["café", "café", "o'zbek", "g'oya", "ma'no"])
        self.assertEqual([t["value"] for t in matching.tokenize("a\u2060b c d e")], ["a", "b", "c", "d", "e"])
        # A ZWSP-only word boundary is ambiguous under the documented heuristic.
        ambiguous = "bir\u200bikki uch tort besh olti"
        self.assertEqual([t["value"] for t in matching.tokenize(ambiguous)],
                         ["birikki", "uch", "tort", "besh", "olti"])
        self.assertIn(matching.INVISIBLE_WARNING,
                      matching.compare(document(ambiguous), [document(ambiguous)])["limitations"])

    def test_invisible_highlight_with_prefix_and_suffix(self):
        original = "😀 Kirish. lo\u200b\u200ctin matn uchun aniq manba nusxa. Yakun."
        result = matching.compare(document(original), [document("lotin matn uchun aniq manba nusxa")])
        span = result["sources"][0]["matches"][0]["document"]
        self.assertEqual(span["start"], original.index("lo"))
        self.assertEqual(span["end"], original.index(". Yakun"))
        self.assertEqual(original[span["start"]:span["end"]], span["text"])

    def test_arabic_marks_warning_in_target_or_source(self):
        plain = "هذا نص عربي واضح للاختبار فقط"
        for mark in ("\u064e", "\u0651", "\u0670", "\u06e7"):
            marked = plain.replace("هذا", "ه" + mark + "ذا")
            for target, source in [(marked, plain), (plain, marked)]:
                result = matching.compare(document(target), [document(source)])
                self.assertIn(matching.ARABIC_WARNING, result["limitations"])
                self.assertEqual(result["document"]["text"], target)
                self.assertEqual(result["sources"][0]["text"], source)
        for text in (plain, "café cafe\u0301 o‘zbek gʻoya maʼno"):
            self.assertNotIn(matching.ARABIC_WARNING,
                             matching.compare(document(text), [document(text)])["limitations"])


    def test_matching_normalization_defaults_to_v2_unchanged(self):
        result = matching.compare(document(TEXT), [document(TEXT)])
        self.assertEqual(result["parameters"]["algorithm_version"], "lexical-shingle-v1")
        self.assertEqual(result["parameters"]["normalization_version"], "uz-latin-v2")

    def test_matching_normalization_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            matching.compare(document(TEXT), [document(TEXT)], matching_normalization="uz-latin-v4")

    def test_v3_matching_finds_morphological_variants_v2_misses(self):
        # Every word differs in suffix only (docs/decisions.md §5): v2 compares
        # the exact casefolded surface form, so no 5-token shingle window can
        # ever be equal and the run is invisible to it. v3-matching compares
        # uz_latin_v3-stemmed keys instead, so the same six words -- sharing a
        # stem pairwise -- form one contiguous run.
        doc_words = ["kitoblarni", "talabalarga", "maktablarda",
                    "universitetlarning", "mashqlarini", "darslarimizda"]
        src_words = ["kitoblardan", "talabalardan", "maktablardan",
                    "universitetlardan", "mashqlaridan", "darslarimizdan"]
        doc_text, src_text = " ".join(doc_words), " ".join(src_words)

        baseline = matching.compare(document(doc_text), [document(src_text)])
        self.assertEqual(baseline["matched_tokens"], 0)

        result = matching.compare(document(doc_text), [document(src_text)],
                                  matching_normalization="uz-latin-v3")
        self.assertEqual(result["matched_tokens"], 6)
        self.assertEqual(result["coverage_percent"], 100.0)
        self.assertEqual(result["parameters"]["algorithm_version"], "lexical-shingle-v2")
        self.assertEqual(result["parameters"]["normalization_version"], "uz-latin-v3")
        match = result["sources"][0]["matches"][0]
        self.assertEqual(match["method"], "shingle")
        # Offset guarantee: the highlighted span is the FULL original word
        # (with its suffix), never the shortened stem used only to find it.
        self.assertEqual(match["document"]["text"], doc_text)
        self.assertEqual(match["source"]["text"], src_text)
        for word in doc_words:
            self.assertIn(word, match["document"]["text"])
        for word in src_words:
            self.assertIn(word, match["source"]["text"])
        for role, original in [("document", doc_text), ("source", src_text)]:
            span = match[role]
            self.assertEqual(original[span["start"]:span["end"]], span["text"])

    def test_v3_matching_does_not_merge_unrelated_words_into_one_stem(self):
        # Collision-safety words already proven distinct in
        # test_uz_latin_v3.py's own collision tests, reused here at the
        # matching stage: a shared stem must not appear by accident among
        # otherwise unrelated five-token runs.
        unrelated_doc = " ".join(["bitiruvchilar", "osmonlarda", "chorrahalarda",
                                  "ko'chalarimizda", "qishloqlarimizga"])
        unrelated_src = " ".join(["non", "suv", "olma", "uzum", "anor"])
        result = matching.compare(document(unrelated_doc), [document(unrelated_src)],
                                  matching_normalization="uz-latin-v3")
        self.assertEqual(result["matched_tokens"], 0)


class ExtractionTests(unittest.TestCase):
    def parse(self, data, name):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "safe-upload"
            path.write_bytes(data)
            return extraction.extract(path, name)

    def test_three_formats_and_positions(self):
        for data, name, kind in [(TEXT.encode(), "a.txt", "paragraph"), (docx(), "a.docx", "paragraph"), (pdf(), "a.pdf", "page")]:
            with self.subTest(name=name):
                result = self.parse(data, name)
                self.assertEqual(result["text"].strip(), TEXT)
                self.assertEqual(result["segments"][0]["kind"], kind)
        text = "Birinchi satr.\r\n\r\n" + TEXT
        result = self.parse(text.encode(), "a.txt")
        self.assertEqual(result["text"], text)
        self.assertEqual(result["segments"][1]["start"], text.index(TEXT))

    def test_failures_are_not_zero_results(self):
        cases = [(b"", "a.txt", "empty"), (b"   ", "a.txt", "empty"),
                 (b"\xff", "a.txt", "encoding"), (b"\x00abc", "a.txt", "invalid_text"),
                 (b"x", "a.exe", "unsupported"), (b"broken", "a.docx", "corrupt"),
                 (b"%PDF-broken", "a.pdf", "corrupt"), (pdf(encrypted=True), "a.pdf", "encrypted"),
                 (pdf(text=""), "a.pdf", "no_text_layer"), (pdf(text="", scan=True), "scan.pdf", "no_text_layer"),
                 (docx(text=""), "a.docx", "empty"), (pdf(), "disguised.txt", "type_mismatch")]
        for data, name, code in cases:
            with self.subTest(name=name, code=code), self.assertRaises(ComparisonError) as raised:
                self.parse(data, name)
            self.assertEqual(raised.exception.code, code)

    def test_second_paragraph_and_pdf_page_coordinates(self):
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        writer.add_page(PdfReader(io.BytesIO(pdf("osmon tog dengiz qush yomgir daraxt"))).pages[0])
        writer.add_page(PdfReader(io.BytesIO(pdf())).pages[0])
        stream = io.BytesIO()
        writer.write(stream)
        for data, name, kind in [(docx("osmon tog dengiz qush yomgir daraxt\n" + TEXT), "a.docx", "paragraph"),
                                 (stream.getvalue(), "a.pdf", "page")]:
            with self.subTest(format=name):
                target = self.parse(data, name)
                result = matching.compare(target, [document(TEXT)])
                span = result["sources"][0]["matches"][0]["document"]
                self.assertEqual(span["location"], {"kind": kind, "from": 2, "to": 2})
                self.assertEqual(target["text"][span["start"]:span["end"]], TEXT)

        from pypdf.errors import DependencyError
        with patch.object(extraction, "PdfReader", side_effect=DependencyError("synthetic crypto dependency")), self.assertRaises(ComparisonError) as raised:
            self.parse(pdf(), "encrypted.pdf")
        self.assertEqual(raised.exception.code, "encrypted")

    def test_docx_xml_entity_and_archive_limits(self):
        malicious = '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///not-to-be-read">]><x>&x;</x>'
        with self.assertRaises(ComparisonError) as raised:
            self.parse(docx(raw_xml=malicious), "a.docx")
        self.assertEqual(raised.exception.code, "corrupt")
        for constant, value in [("MAX_ZIP_BYTES", 100), ("MAX_XML_BYTES", 10), ("MAX_ZIP_ENTRIES", 1)]:
            with self.subTest(constant=constant), patch.object(extraction, constant, value), self.assertRaises(ComparisonError) as raised:
                self.parse(docx(), "a.docx")
            self.assertEqual(raised.exception.code, "archive_limit")

    def test_docx_split_runs_tables_and_textbox_not_duplicated(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Ilmiy </w:t></w:r><w:r><w:t>hujjat</w:t></w:r>'
               '<w:r><w:drawing><w:txbxContent><w:p><w:r><w:t>excluded</w:t></w:r></w:p></w:txbxContent></w:drawing></w:r></w:p>'
               '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>jadval matni</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
               '</w:body></w:document>')
        parsed = self.parse(docx(raw_xml=xml), "table.docx")
        self.assertEqual(parsed["text"], "Ilmiy hujjat\n\njadval matni")
        self.assertEqual(len(parsed["segments"]), 2)

    def test_file_text_and_page_limits(self):
        with self.assertRaises(ComparisonError) as raised:
            self.parse(b"a" * (MAX_FILE_BYTES + 1), "a.txt")
        self.assertEqual(raised.exception.code, "file_limit")
        with patch.object(extraction, "MAX_TEXT_CHARS", 10), self.assertRaises(ComparisonError) as raised:
            self.parse(TEXT.encode(), "a.txt")
        self.assertEqual(raised.exception.code, "text_limit")
        with patch.object(extraction, "MAX_PAGES", 0), self.assertRaises(ComparisonError) as raised:
            self.parse(pdf(), "a.pdf")
        self.assertEqual(raised.exception.code, "page_limit")


class UploadTests(unittest.TestCase):
    def parse(self, files, chunk_size=13, truncate=False):
        body, content_type = multipart(files)
        with tempfile.TemporaryDirectory() as folder:
            upload = uploads.Uploads(Path(folder), content_type)
            try:
                data = body[:-10] if truncate else body
                for start in range(0, len(data), chunk_size):
                    upload.write(data[start:start + chunk_size])
                return upload.finish()
            finally:
                upload.close()

    def test_streaming_safe_paths_and_count(self):
        result = self.parse([("sources", "source.txt", TEXT.encode()), ("document", "../../target.txt", TEXT.encode())])
        self.assertEqual(result[0]["name"], "target.txt")
        self.assertEqual(result[0]["path"], "upload-1")
        for files in [[("sources", "a.txt", b"x")] * 6,
                      [("document", "a.txt", b"x")] * 2 + [("sources", "b.txt", b"x")],
                      [("document", "a.txt", b"x")] + [("sources", "b.txt", b"x")] * 6]:
            with self.assertRaises(ComparisonError):
                self.parse(files)
        with self.assertRaises(ComparisonError):
            self.parse([("document", "a.txt", b"x"), ("sources", "b.txt", b"x")], truncate=True)

    def test_document_without_manual_sources_is_allowed_by_the_parser(self):
        # Whether a source is required at all (manual or corpus) is enforced by the
        # caller (api.compare_uploads), which knows include_corpus; the raw upload
        # parser only bounds the count (0-5), it does not require at least one.
        result = self.parse([("document", "a.txt", b"x")])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["role"], "document")

    def test_actual_file_and_total_boundaries(self):
        for size, fail in [(MAX_FILE_BYTES, False), (MAX_FILE_BYTES + 1, True)]:
            files = [("document", "a.txt", b"a" * size), ("sources", "b.txt", b"b")]
            if fail:
                with self.assertRaises(ComparisonError) as raised:
                    self.parse(files, chunk_size=65536)
                self.assertEqual(raised.exception.code, "file_limit")
            else:
                self.assertEqual(len(self.parse(files, chunk_size=65536)), 2)
        files = [("document", "a.txt", b"a" * MAX_FILE_BYTES)] + [("sources", f"s{i}.txt", b"b" * MAX_FILE_BYTES) for i in range(2)]
        self.assertEqual(len(self.parse(files, chunk_size=65536)), 3)
        with self.assertRaises(ComparisonError) as raised:
            self.parse(files + [("sources", "extra.txt", b"x")], chunk_size=65536)
        self.assertEqual(raised.exception.code, "total_limit")


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, body, content_type):
        sent = False
        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        request = Request({"type": "http", "method": "POST", "scheme": "http", "path": "/compare",
                           "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                           "headers": [(b"content-type", content_type.encode()), (b"x-antiplagiat-local", b"1"),
                                       (b"idempotency-key", str(uuid.uuid4()).encode())]}, receive)
        return await api.compare_uploads(request)

    async def test_cleanup_success_error_and_malformed_upload(self):
        body, content_type = multipart([("document", "a.txt", TEXT.encode()), ("sources", "b.txt", TEXT.encode())])
        original = tempfile.TemporaryDirectory
        seen = []
        def temporary(**kwargs):
            directory = original(**kwargs)
            seen.append(directory.name)
            return directory
        for failure in (None, ComparisonError("timeout", "timeout")):
            with patch.object(api.tempfile, "TemporaryDirectory", side_effect=temporary), patch.object(api, "run_worker", return_value={"status": "completed"}, side_effect=failure):
                response = await self.request(body, content_type)
                self.assertEqual(response.status_code, 422 if failure else 200)
            self.assertTrue(all(not Path(path).exists() for path in seen))
        with patch.object(api.tempfile, "TemporaryDirectory", side_effect=temporary):
            response = await self.request(body[:-10], content_type)
            self.assertEqual(response.status_code, 400)
        self.assertTrue(all(not Path(path).exists() for path in seen))
        self.assertFalse(api.gate.locked())

    async def test_neither_manual_sources_nor_corpus_is_rejected_before_any_work(self):
        body, content_type = multipart([("document", "a.txt", TEXT.encode())])
        with patch.object(api, "run_worker") as worker:
            response = await self.request(body, content_type)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(worker.called)
        self.assertFalse(api.gate.locked())

    def setUp(self):
        self.patches = [patch.object(api.auth, "require_user", return_value={"id": str(uuid.uuid4())}),
                        patch.object(api.reports, "retry", return_value=None),
                        patch.object(api.reports, "save", side_effect=lambda owner, key, digest, result: result)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    async def test_database_failure_after_worker_cleans_resources(self):
        from backend.persistence import ServiceError
        body, content_type = multipart([("document", "a.txt", TEXT.encode()), ("sources", "b.txt", TEXT.encode())])
        original = tempfile.TemporaryDirectory
        seen = []
        def temporary(**kwargs):
            result = original(**kwargs)
            seen.append(result.name)
            return result
        with patch.object(api.tempfile, "TemporaryDirectory", side_effect=temporary), \
                patch.object(api, "run_worker", return_value={"status": "completed"}), \
                patch.object(api.reports, "save", side_effect=ServiceError("database_unavailable", "private DB failure", 503)):
            with self.assertRaises(ServiceError):
                await self.request(body, content_type)
        self.assertTrue(seen and all(not Path(path).exists() for path in seen))
        self.assertFalse(api.gate.locked())


class WorkerTests(unittest.TestCase):
    def test_real_worker_and_memory_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            items = []
            for i in range(2):
                (folder / str(i)).write_text(TEXT, encoding="utf-8")
                items.append({"path": str(i), "name": f"{i}.txt"})
            self.assertEqual(runner.run_worker(folder, items)["coverage_percent"], 100)
        code = "from backend.comparison.resources import restrict_worker\nrestrict_worker()\ntry:\n bytearray(600*1024*1024)\nexcept MemoryError:\n print('limited')\n"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "limited")

    def test_timeout_kills_owned_worker(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner.policy, "WORKER_SECONDS", 0.00001):
            with self.assertRaises(ComparisonError) as raised:
                runner.run_worker(Path(directory), [])
            self.assertEqual(raised.exception.code, "timeout")

    def test_timeout_message_uses_current_policy_and_fraction(self):
        for seconds, expected in [(30, "30"), (2.5, "2.5"), (0.125, "0.125")]:
            process = MagicMock()
            process.__enter__.return_value = process
            process.wait.side_effect = [subprocess.TimeoutExpired("worker", seconds), None]
            process.poll.return_value = -1
            with self.subTest(seconds=seconds), tempfile.TemporaryDirectory() as directory, \
                    patch.object(runner.policy, "WORKER_SECONDS", seconds), \
                    patch.object(runner.subprocess, "Popen", return_value=process):
                with self.assertRaises(ComparisonError) as raised:
                    runner.run_worker(Path(directory), [])
                self.assertEqual(raised.exception.message, f"Qayta ishlash {expected} soniya chegarasidan oshdi.")
                self.assertEqual(process.wait.call_args_list[0].kwargs, {"timeout": seconds})
                process.kill.assert_called_once()


if __name__ == "__main__":
    unittest.main()
