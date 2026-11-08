"""Corpus integration against a real, owned, disposable PostgreSQL cluster.

Never touches an existing database. All documents are synthetic.
"""
import asyncio
import json
import secrets
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

from backend import corpus, corpus_api, manage, persistence
from backend.comparison import api
from backend.tests.fixtures import docx, multipart, pdf
from backend.tests.postgres_fixture import isolated_postgres, runtime_environment

UZ = ("Ilmiy tadqiqot ishida matn oxshashligini aniqlash usullari batafsil tahlil qilinadi "
      "va olingan natijalar jadval korinishida keltiriladi hamda xulosalar asoslanadi")
RU = ("Nauchnaya rabota soderzhit analiz metodov opredeleniya shodstva teksta "
      "i rezultaty predstavleny v tablice s obosnovaniem vyvodov avtora")
EN = ("This research paper analyses lexical similarity detection methods and reports "
      "the measured outcomes in a table together with the reasoning behind each conclusion")
UNRELATED = ("Bogda olma anor va uzum pishdi dehqonlar hosilni yigib omborga joyladi "
             "ertalab yomgir yogdi va havo salqin boldi deb aytishdi qishloqda")


def corpus_metadata(title, **extra):
    return {"title": title, "author_display": "Sinov Muallif", "doc_type": "bmi", "year": 2024,
            "language_hint": "uz", "source_note": "sintetik", "original_filename": title + ".txt",
            "permission_basis": "Sintetik sinov uchun akademiya ruxsati", **extra}


def extracted(text, name):
    return {"name": name, "format": "txt", "text": text,
            "segments": [{"kind": "paragraph", "number": 1, "start": 0, "end": len(text)}]}


CLUSTER = {}


def setUpModule():
    """One owned disposable cluster for the whole module."""
    CLUSTER["handle"] = isolated_postgres()
    CLUSTER["admin"], CLUSTER["runtime"] = CLUSTER["handle"].__enter__()
    manage.migrate(CLUSTER["admin"])
    CLUSTER["admin_id"] = manage.create_user(CLUSTER["admin"], "corpus.admin",
                                             secrets.token_urlsafe(24), role="admin")
    CLUSTER["user_id"] = manage.create_user(CLUSTER["admin"], "corpus.reader",
                                            secrets.token_urlsafe(24))
    CLUSTER["manager_id"] = manage.create_user(CLUSTER["admin"], "corpus.manager",
                                               secrets.token_urlsafe(24), role="corpus_manager")
    CLUSTER["reviewer_id"] = manage.create_user(CLUSTER["admin"], "corpus.reviewer",
                                                secrets.token_urlsafe(24), role="reviewer")


def tearDownModule():
    CLUSTER["handle"].__exit__(None, None, None)


class CorpusFixture:
    """Shared helpers; not a TestCase so suites do not re-run each other's tests."""

    def setUp(self):
        self.admin = CLUSTER["admin"]
        self.runtime = CLUSTER["runtime"]
        self.admin_id = CLUSTER["admin_id"]
        self.user_id = CLUSTER["user_id"]
        self.manager_id = CLUSTER["manager_id"]
        self.reviewer_id = CLUSTER["reviewer_id"]
        self.environment = runtime_environment(self.runtime)
        self.environment.__enter__()
        self.addCleanup(self.environment.__exit__, None, None, None)

    def unique(self, text):
        # Distinct content per test; the digest uniqueness rule is tested on purpose.
        return f"{text} sinovbelgisi{uuid.uuid4().hex[:10]}"

    def add(self, text, title, raw=None, visibility=None):
        metadata = corpus_metadata(title, **({"visibility": visibility} if visibility else {}))
        return corpus.add_document(metadata, extracted(text, title),
                                   self.admin_id, raw if raw is not None else text.encode())


class CorpusDatabaseTests(CorpusFixture, unittest.TestCase):

    def test_add_builds_chunks_and_a_searchable_index(self):
        text = self.unique(UZ)
        stored = self.add(text, "uz-" + uuid.uuid4().hex[:8])
        self.assertGreaterEqual(stored["chunk_count"], 1)
        with persistence.database(self.admin) as conn:
            row = conn.execute("SELECT char_count, token_count, extraction_policy, status, segments"
                               " FROM antiplagiat.corpus_documents WHERE id=%s", (stored["id"],)).fetchone()
            chunks = conn.execute("SELECT chunk_text, char_start, char_end, fts IS NOT NULL AS indexed"
                                  " FROM antiplagiat.corpus_chunks WHERE corpus_document_id=%s"
                                  " ORDER BY chunk_index", (stored["id"],)).fetchall()
        self.assertEqual(row["char_count"], len(text))
        self.assertEqual(row["extraction_policy"], "uz-latin-v2")
        self.assertEqual(row["status"], "active")
        self.assertEqual(len(chunks), stored["chunk_count"])
        for chunk in chunks:
            self.assertTrue(chunk["indexed"])
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])

    def test_visibility_defaults_to_excerpt_and_rejects_unknown_values(self):
        text = self.unique(UZ)
        stored = self.add(text, "vis-default-" + uuid.uuid4().hex[:8])
        with persistence.database(self.admin) as conn:
            row = conn.execute("SELECT visibility FROM antiplagiat.corpus_documents WHERE id=%s",
                               (stored["id"],)).fetchone()
        self.assertEqual(row["visibility"], "excerpt")
        with self.assertRaises(corpus.CorpusError) as raised:
            corpus.add_document(corpus_metadata("vis-bad", visibility="public"),
                                extracted(self.unique(UZ), "vis-bad"), self.admin_id, b"x")
        self.assertEqual(raised.exception.code, "corpus_metadata")

    def test_metadata_only_visibility_is_stored_and_immutable_through_the_app(self):
        text = self.unique(UZ)
        stored = self.add(text, "vis-meta-" + uuid.uuid4().hex[:8], visibility="metadata_only")
        with persistence.database(self.admin) as conn:
            row = conn.execute("SELECT visibility FROM antiplagiat.corpus_documents WHERE id=%s",
                               (stored["id"],)).fetchone()
        self.assertEqual(row["visibility"], "metadata_only")
        # The runtime role has no UPDATE grant on this column at all (see
        # backend/manage.py's migrate()), so the app can never flip it post-ingest.
        with self.assertRaises(persistence.ServiceError):
            with persistence.database(self.runtime) as conn:
                conn.execute("UPDATE antiplagiat.corpus_documents SET visibility='excerpt' WHERE id=%s",
                             (stored["id"],))

    def test_v3_column_is_populated_without_changing_original_text_or_offsets(self):
        """uz-latin-v3 stays retrieval-only: proven, not claimed.

        extracted_text, segments and every chunk's (char_start, char_end,
        chunk_text) slice of the original text must come out byte-identical
        to the v2-only behaviour already covered by
        test_add_builds_chunks_and_a_searchable_index. The new
        chunk_text_uz_latin_v3 column is additional, and for a text with
        real Uzbek suffixes it must actually differ from chunk_text in at
        least one chunk -- otherwise this test would pass even if v3 were
        never wired up.
        """
        text = self.unique(UZ)
        stored = self.add(text, "v3col-" + uuid.uuid4().hex[:8])
        with persistence.database(self.admin) as conn:
            doc = conn.execute("SELECT extracted_text, segments FROM antiplagiat.corpus_documents"
                               " WHERE id=%s", (stored["id"],)).fetchone()
            chunks = conn.execute(
                "SELECT chunk_text, chunk_text_uz_latin_v3, char_start, char_end, "
                "fts_v3 IS NOT NULL AS v3_indexed FROM antiplagiat.corpus_chunks"
                " WHERE corpus_document_id=%s ORDER BY chunk_index", (stored["id"],)).fetchall()
        self.assertEqual(doc["extracted_text"], text)
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])
            self.assertTrue(chunk["v3_indexed"])
            self.assertIsNotNone(chunk["chunk_text_uz_latin_v3"])
        self.assertTrue(any(c["chunk_text_uz_latin_v3"] != c["chunk_text"] for c in chunks),
                        "v3 stemming never fired on a text with ordinary Uzbek suffixes")

    def test_v3_retrieval_never_changes_what_the_comparison_highlights(self):
        """Whichever normalization retrieval used, the highlighted span is
        decided only by matching.compare() on the untouched original text.
        """
        from backend.comparison.matching import compare, tokenize
        source_text = self.unique(UZ)
        stored = self.add(source_text, "v3cmp-" + uuid.uuid4().hex[:8])
        query_text = source_text  # verbatim query: both normalizations must find it
        qtokens = tokenize(query_text)
        spans_by_normalization = {}
        for normalization in ("v2", "v3"):
            found, _ = corpus.candidates(qtokens, normalization=normalization, text=query_text)
            self.assertIn(stored["id"], [c["id"] for c in found])
            loaded = corpus.load_for_comparison(stored["id"])
            result = compare(extracted(query_text, "q.txt"), [loaded])
            spans_by_normalization[normalization] = [
                (m["document"]["start"], m["document"]["end"], m["document"]["text"])
                for m in result["sources"][0]["matches"]]
        self.assertEqual(spans_by_normalization["v2"], spans_by_normalization["v3"])
        self.assertTrue(spans_by_normalization["v2"])  # the test is vacuous if nothing matched

    def test_duplicate_content_is_refused_until_the_first_copy_is_withdrawn(self):
        raw = (UZ + " takroriy").encode()
        first = self.add(UZ + " takroriy", "dup-a", raw)
        with self.assertRaises(corpus.CorpusError) as raised:
            self.add(UZ + " takroriy", "dup-b", raw)
        self.assertEqual((raised.exception.status, raised.exception.code), (409, "corpus_duplicate"))
        corpus.withdraw(first["id"])
        again = self.add(UZ + " takroriy", "dup-c", raw)
        self.assertNotEqual(again["id"], first["id"])

    def test_withdraw_purges_text_and_removes_the_document_from_retrieval(self):
        from backend.comparison.matching import tokenize
        text = self.unique(RU)
        stored = self.add(text, "ru-" + uuid.uuid4().hex[:8])
        tokens = tokenize(text)
        found, _ = corpus.candidates(tokens)
        self.assertIn(stored["id"], [c["id"] for c in found])
        corpus.withdraw(stored["id"])
        found_after, _ = corpus.candidates(tokens)
        self.assertNotIn(stored["id"], [c["id"] for c in found_after])
        self.assertIsNone(corpus.load_for_comparison(stored["id"]))
        with persistence.database(self.admin) as conn:
            row = conn.execute("SELECT extracted_text, status, withdrawn_at FROM antiplagiat.corpus_documents"
                               " WHERE id=%s", (stored["id"],)).fetchone()
            texts = conn.execute("SELECT DISTINCT chunk_text, chunk_text_uz_latin_v3"
                                 " FROM antiplagiat.corpus_chunks WHERE corpus_document_id=%s",
                                 (stored["id"],)).fetchall()
        self.assertIsNone(row["extracted_text"])
        self.assertEqual(row["status"], "withdrawn")
        self.assertIsNotNone(row["withdrawn_at"])
        self.assertEqual([t["chunk_text"] for t in texts], [""])
        self.assertEqual([t["chunk_text_uz_latin_v3"] for t in texts], [""])
        found_v3_after, _ = corpus.candidates(tokens, normalization="v3", text=text)
        self.assertNotIn(stored["id"], [c["id"] for c in found_v3_after])
        with self.assertRaises(corpus.CorpusError):
            corpus.withdraw(stored["id"])

    def test_retrieval_ranks_the_matching_language_above_unrelated_text(self):
        from backend.comparison.matching import tokenize
        stored, bodies = {}, {}
        for text, label in [(UZ, "uz"), (RU, "ru"), (EN, "en"), (UNRELATED, "other")]:
            bodies[label] = self.unique(text)
            stored[label] = self.add(bodies[label], f"ret-{label}-" + uuid.uuid4().hex[:6])["id"]
        for label in ("uz", "ru", "en"):
            with self.subTest(language=label):
                found, limit = corpus.candidates(tokenize(bodies[label]))
                self.assertLessEqual(len(found), limit)
                ranked = [c["id"] for c in found]
                self.assertIn(stored[label], ranked)
                if stored["other"] in ranked:
                    self.assertLess(ranked.index(stored[label]), ranked.index(stored["other"]))

    def test_unrelated_document_produces_no_matching_passage(self):
        from backend.comparison.matching import tokenize
        body = self.unique(UZ)
        stored = self.add(body, "neg-" + uuid.uuid4().hex[:8])
        far = ("kompyuter tarmogi protokol server marshrutizator kabel signal uzatish tezligi oshdi "
               "va yangi uskunalar sinovdan otkazildi deb qayd etildi hisobotda")
        found, _ = corpus.candidates(tokenize(far))
        if stored["id"] in [c["id"] for c in found]:
            # Retrieval may still rank it; the shingle algorithm must find nothing.
            from backend.comparison.matching import compare
            loaded = corpus.load_for_comparison(stored["id"])
            result = compare(extracted(far, "far.txt"), [loaded])
            self.assertEqual(result["coverage_percent"], 0.0)
            self.assertEqual(result["sources"][0]["matches"], [])

    def test_listing_and_withdrawn_filter(self):
        stored = self.add(self.unique(EN), "list-" + uuid.uuid4().hex[:8])
        active = corpus.list_documents(1, "active")
        self.assertIn(stored["id"], [i["id"] for i in active["items"]])
        corpus.withdraw(stored["id"])
        self.assertNotIn(stored["id"], [i["id"] for i in corpus.list_documents(1, "active")["items"]])
        self.assertIn(stored["id"], [i["id"] for i in corpus.list_documents(1, "withdrawn")["items"]])

    def test_runtime_role_cannot_delete_or_rewrite_corpus_provenance(self):
        stored = self.add(self.unique(UZ + " himoya"), "guard-" + uuid.uuid4().hex[:8])
        attempts = [("delete", "DELETE FROM antiplagiat.corpus_documents WHERE id=%s"),
                    ("rewrite permission", "UPDATE antiplagiat.corpus_documents SET permission_basis='x' WHERE id=%s"),
                    ("rewrite digest", "UPDATE antiplagiat.corpus_documents SET content_sha256=repeat('0',64) WHERE id=%s"),
                    ("delete chunks", "DELETE FROM antiplagiat.corpus_chunks WHERE corpus_document_id=%s")]
        for label, statement in attempts:
            with self.subTest(attempt=label), self.assertRaises(Exception):
                with persistence.database(self.runtime) as conn:
                    conn.execute(statement, (stored["id"],))


class CorpusUploadFormatTests(CorpusFixture, unittest.TestCase):
    """POST /corpus/documents end-to-end (corpus_api.add -> ingest() ->
    run_worker(mode="extract") -> corpus.add_document()), through the
    sandboxed extraction worker -- never exercised by CorpusDatabaseTests,
    which bypasses extraction entirely by calling corpus.add_document()
    directly with a hand-built "extracted" dict. Covers every format the
    admin corpus upload endpoint accepts (TXT/DOCX/PDF, see
    backend/corpus_api.py's CorpusUpload.headers_finished()), plus the
    scanned-PDF rejection (no text layer -> no OCR -> explicit error, never
    an empty/near-empty corpus document).
    """

    def corpus_upload(self, name, content, **field_overrides):
        fields = {"title": "upload-" + uuid.uuid4().hex[:8], "author_display": "Sinov Muallif",
                  "doc_type": "bmi", "year": "2024", "language_hint": "uz", "source_note": "sinov",
                  "permission_basis": "Sinov uchun akademiya ruxsati", **field_overrides}
        body, kind = multipart([("file", name, content)] +
                               [(field, field, value.encode()) for field, value in fields.items()])
        sent = False

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        scope = {"type": "http", "method": "POST", "scheme": "http", "path": "/corpus/documents",
                 "query_string": b"", "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                 "headers": [(b"content-type", kind.encode()), (b"content-length", str(len(body)).encode())]}
        with patch.object(corpus_api.auth, "require_corpus_manager",
                          return_value={"id": str(self.manager_id), "role": "corpus_manager"}):
            return asyncio.run(corpus_api.add(Request(scope, receive)))

    def payload(self, response):
        return json.loads(bytes(response.body))

    def stored_row(self, document_id):
        with persistence.database(self.admin) as conn:
            doc = conn.execute("SELECT extracted_text, segments, char_count FROM antiplagiat.corpus_documents"
                               " WHERE id=%s", (document_id,)).fetchone()
            chunks = conn.execute("SELECT chunk_text, char_start, char_end FROM antiplagiat.corpus_chunks"
                                  " WHERE corpus_document_id=%s ORDER BY chunk_index", (document_id,)).fetchall()
        return doc, chunks

    def test_txt_upload_through_the_real_endpoint(self):
        # The only format CorpusDatabaseTests' self.add() already covers --
        # but that helper skips extraction; this goes through the real
        # endpoint (including the sandboxed worker) for the first time.
        text = self.unique(UZ)
        response = self.corpus_upload("real.txt", text.encode())
        self.assertEqual(response.status_code, 200)
        stored = self.payload(response)
        doc, chunks = self.stored_row(stored["id"])
        self.assertEqual(doc["extracted_text"], text)
        self.assertEqual(doc["char_count"], len(text))
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])

    def test_docx_upload_preserves_text_segments_and_offsets(self):
        text = self.unique(UZ)
        response = self.corpus_upload("real.docx", docx(text=text))
        self.assertEqual(response.status_code, 200)
        stored = self.payload(response)
        doc, chunks = self.stored_row(stored["id"])
        self.assertEqual(doc["extracted_text"], text)
        self.assertEqual(doc["segments"][0]["kind"], "paragraph")
        self.assertGreaterEqual(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])

    def test_pdf_with_text_layer_preserves_text_segments_and_offsets(self):
        text = self.unique(EN)
        response = self.corpus_upload("real.pdf", pdf(text=text))
        self.assertEqual(response.status_code, 200)
        stored = self.payload(response)
        doc, chunks = self.stored_row(stored["id"])
        self.assertEqual(doc["extracted_text"], text)
        self.assertEqual(doc["segments"][0]["kind"], "page")
        self.assertGreaterEqual(len(chunks), 1)
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])

    def test_scanned_pdf_is_rejected_not_ingested_as_empty(self):
        before = len(corpus.list_documents(1, "active")["items"])
        response = self.corpus_upload("scan.pdf", pdf(text="", scan=True))
        self.assertEqual(response.status_code, 422)
        error = self.payload(response)["error"]
        self.assertEqual(error["code"], "no_text_layer")
        self.assertEqual(error["file"], "scan.pdf")
        # No partial/empty document was left behind -- ingest() never even
        # reached corpus.add_document(), since extraction failed first.
        self.assertEqual(len(corpus.list_documents(1, "active")["items"]), before)

    def test_blank_pdf_without_any_text_is_rejected_the_same_way(self):
        response = self.corpus_upload("blank.pdf", pdf(text=""))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.payload(response)["error"]["code"], "no_text_layer")


class CorpusBatchIngestTests(CorpusFixture, unittest.TestCase):
    """backend.manage.corpus_add_batch(): many files/folders in one CLI run,
    shared metadata, one result per file, one bad file never stops the rest.
    """

    SHARED_INPUTS = ["Sinov Muallif", "bmi", "uz", "sinov", "Sinov uchun akademiya ruxsati", "", ""]

    def write(self, folder, name, content):
        path = Path(folder) / name
        path.write_bytes(content)
        return path

    def test_mixed_batch_reports_added_duplicate_and_error_per_file_and_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            existing_text = self.unique(UZ)
            self.add(existing_text, "pre-existing-" + uuid.uuid4().hex[:8], raw=existing_text.encode())
            good_txt = self.write(folder, "a-good.txt", self.unique(EN).encode())
            good_docx = self.write(folder, "b-good.docx", docx(text=self.unique(UZ)))
            duplicate = self.write(folder, "c-duplicate.txt", existing_text.encode())
            bad_scan = self.write(folder, "d-scan.pdf", pdf(text="", scan=True))
            with patch("builtins.input", side_effect=list(self.SHARED_INPUTS)):
                results = manage.corpus_add_batch(self.admin, [folder], "corpus.manager")
            by_name = {Path(r["path"]).name: r for r in results}
            self.assertEqual(len(results), 4)
            self.assertEqual(by_name["a-good.txt"]["status"], "added")
            self.assertEqual(by_name["b-good.docx"]["status"], "added")
            self.assertEqual(by_name["c-duplicate.txt"]["status"], "duplicate")
            self.assertEqual(by_name["d-scan.pdf"]["status"], "error")
            self.assertEqual(by_name["d-scan.pdf"]["code"], "no_text_layer")
            # Both successes actually persisted, with the filename stem as title.
            with persistence.database(self.admin) as conn:
                titles = {row["original_filename"]: row["title"] for row in conn.execute(
                    "SELECT original_filename, title FROM antiplagiat.corpus_documents WHERE id = ANY(%s)",
                    ([by_name["a-good.txt"]["id"], by_name["b-good.docx"]["id"]],)).fetchall()}
            self.assertEqual(titles["a-good.txt"], "a-good")
            self.assertEqual(titles["b-good.docx"], "b-good")

    def test_one_file_failing_does_not_stop_files_that_come_after_it(self):
        with tempfile.TemporaryDirectory() as folder:
            # Empty .txt matches the batch's own extension filter (so the
            # directory scan does not silently skip it, unlike an
            # unsupported extension -- see test_a_single_file_path_and_a_
            # directory_can_be_combined) but fails extraction ("empty").
            self.write(folder, "a-bad.txt", b"")
            self.write(folder, "b-good.txt", self.unique(RU).encode())
            with patch("builtins.input", side_effect=list(self.SHARED_INPUTS)):
                results = manage.corpus_add_batch(self.admin, [folder], "corpus.manager")
            by_name = {Path(r["path"]).name: r for r in results}
            self.assertEqual(by_name["a-bad.txt"]["status"], "error")
            self.assertEqual(by_name["a-bad.txt"]["code"], "empty")
            self.assertEqual(by_name["b-good.txt"]["status"], "added")

    def test_missing_permission_basis_aborts_before_touching_any_file(self):
        with tempfile.TemporaryDirectory() as folder:
            tag = uuid.uuid4().hex[:8]
            self.write(folder, f"a-{tag}.txt", self.unique(UZ).encode())
            self.write(folder, f"b-{tag}.txt", self.unique(EN).encode())
            inputs = ["Sinov Muallif", "bmi", "uz", "sinov", "", ""]  # empty permission_basis
            with patch("builtins.input", side_effect=inputs):
                with self.assertRaises(ValueError):
                    manage.corpus_add_batch(self.admin, [folder], "corpus.manager")
            with persistence.database(self.admin) as conn:
                found = conn.execute("SELECT count(*) AS n FROM antiplagiat.corpus_documents"
                                     " WHERE original_filename IN (%s, %s)",
                                     (f"a-{tag}.txt", f"b-{tag}.txt")).fetchone()
            self.assertEqual(found["n"], 0)

    def test_a_single_file_path_and_a_directory_can_be_combined(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "inside.txt", self.unique(UZ).encode())
            self.write(folder, "ignored.md", b"not a corpus format, but inside a directory -- skipped silently")
            with tempfile.TemporaryDirectory() as other:
                standalone = self.write(other, "standalone.txt", self.unique(EN).encode())
                with patch("builtins.input", side_effect=list(self.SHARED_INPUTS)):
                    results = manage.corpus_add_batch(self.admin, [folder, str(standalone)], "corpus.manager")
            by_name = {Path(r["path"]).name: r for r in results}
            self.assertEqual(set(by_name), {"inside.txt", "standalone.txt"})  # ignored.md never appears
            self.assertEqual(by_name["inside.txt"]["status"], "added")
            self.assertEqual(by_name["standalone.txt"]["status"], "added")

    def test_requires_admin_or_corpus_manager_account(self):
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, "a.txt", self.unique(UZ).encode())
            with patch("builtins.input", side_effect=list(self.SHARED_INPUTS)):
                with self.assertRaises(ValueError):
                    manage.corpus_add_batch(self.admin, [folder], "corpus.reader")


class CorpusComparisonTests(CorpusFixture, unittest.TestCase):
    """The compare endpoint with the corpus flag off and on."""

    def request(self, body, content_type, include_corpus=False, role="user", normalization="v2",
                idempotency_key=None):
        sent = False
        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        query = []
        if include_corpus:
            query.append("include_corpus=true")
        if normalization != "v2":
            query.append(f"normalization={normalization}")
        scope = {"type": "http", "method": "POST", "scheme": "http", "path": "/compare",
                 "query_string": "&".join(query).encode(),
                 "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                 "headers": [(b"content-type", content_type.encode()), (b"x-antiplagiat-local", b"1"),
                             (b"idempotency-key", (idempotency_key or str(uuid.uuid4())).encode())]}
        owner = str(self.admin_id if role == "admin" else self.user_id)
        with patch.object(api.auth, "require_user", return_value={"id": owner, "role": role}):
            return asyncio.run(api.compare_uploads(Request(scope, receive), include_corpus=include_corpus,
                                                    normalization=normalization))

    def payload(self, response):
        return json.loads(bytes(response.body))

    def test_flag_off_keeps_the_existing_result_shape(self):
        self.add(self.unique(UZ), "off-" + uuid.uuid4().hex[:8])
        body, kind = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UZ.encode())])
        result = self.payload(self.request(body, kind))
        self.assertEqual(result["coverage_percent"], 100.0)
        self.assertEqual(len(result["sources"]), 1)
        self.assertNotIn("corpus", result)
        self.assertNotIn("excerpt_policy", result)
        self.assertTrue(all("corpus" not in s for s in result["sources"]))

    def test_flag_on_adds_the_corpus_candidate_with_usable_offsets(self):
        stored = self.add(UZ, "on-" + uuid.uuid4().hex[:8])
        document = UZ + " Qoshimcha mustaqil xulosa qismi bu yerda yozilgan."
        body, kind = multipart([("document", "t.txt", document.encode()),
                                ("sources", "s.txt", UNRELATED.encode())])
        result = self.payload(self.request(body, kind, include_corpus=True))
        self.assertEqual(result["corpus"]["retrieval_policy"], "pg-fts-candidate-v1")
        self.assertEqual(result["corpus"]["fts_configuration"], "simple")
        self.assertGreaterEqual(result["corpus"]["candidates_compared"], 1)
        self.assertTrue(any("limit tufayli" in line for line in result["limitations"]))
        corpus_sources = [s for s in result["sources"] if s.get("corpus")]
        self.assertEqual(len(corpus_sources), result["corpus"]["candidates_compared"])
        source = next(s for s in corpus_sources if s["corpus"]["id"] == stored["id"])
        self.assertTrue(source["matches"])
        match = source["matches"][0]
        self.assertEqual(result["document"]["text"][match["document"]["start"]:match["document"]["end"]],
                         match["document"]["text"])
        self.assertIn(match["source"]["text"], UZ)
        self.assertGreater(source["coverage_percent"], 0)
        self.assertLessEqual(result["coverage_percent"], 100.0)

    def test_corpus_only_without_manual_sources_succeeds(self):
        unique_uz = self.unique(UZ)
        stored = self.add(unique_uz, "corpus-only-" + uuid.uuid4().hex[:8])
        document = unique_uz + " Qoshimcha mustaqil xulosa qismi bu yerda yozilgan."
        body, kind = multipart([("document", "t.txt", document.encode())])
        result = self.payload(self.request(body, kind, include_corpus=True))
        self.assertGreaterEqual(result["corpus"]["candidates_compared"], 1)
        corpus_sources = [s for s in result["sources"] if s.get("corpus")]
        self.assertEqual(len(corpus_sources), result["corpus"]["candidates_compared"])
        self.assertTrue(any(s["corpus"]["id"] == stored["id"] for s in corpus_sources))
        self.assertGreater(result["coverage_percent"], 0)

    def test_neither_manual_sources_nor_corpus_is_rejected(self):
        body, kind = multipart([("document", "t.txt", UZ.encode())])
        response = self.request(body, kind, include_corpus=False)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.payload(response)["error"]["code"], "no_sources")

    def test_normalization_defaults_to_v2_and_v3_is_recorded_when_requested(self):
        self.add(self.unique(UZ), "norm-" + uuid.uuid4().hex[:8])
        body, kind = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UNRELATED.encode())])
        default_result = self.payload(self.request(body, kind, include_corpus=True))
        self.assertEqual(default_result["corpus"]["normalization"], "v2")
        self.assertFalse(any("uz-latin-v3" in line for line in default_result["limitations"]))
        body2, kind2 = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UNRELATED.encode())])
        v3_result = self.payload(self.request(body2, kind2, include_corpus=True, normalization="v3"))
        self.assertEqual(v3_result["corpus"]["normalization"], "v3")
        self.assertTrue(any("uz-latin-v3" in line for line in v3_result["limitations"]))

    def test_normalization_rejects_unknown_value(self):
        body, kind = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UNRELATED.encode())])
        response = self.request(body, kind, include_corpus=True, normalization="v4")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.payload(response)["error"]["code"], "normalization_invalid")

    def test_normalization_v3_without_corpus_is_ignored_not_an_error(self):
        body, kind = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UZ.encode())])
        result = self.payload(self.request(body, kind, include_corpus=False, normalization="v3"))
        self.assertNotIn("corpus", result)  # corpus retrieval never ran; nothing to normalize

    def test_v3_matching_finds_what_v3_retrieval_only_misses(self):
        # Stored and checked text share every content word's STEM but use
        # different suffixes throughout (docs/decisions.md §5): "v3" finds
        # the candidate via retrieval (fts_v3) but still matches with the
        # unchanged v2 exact/shingle algorithm, so the morphological run is
        # never flagged. "v3-matching" additionally matches through
        # uz-latin-v3-stemmed keys, so the same run IS flagged -- and still
        # highlights the full, original, checked-side word (with its own
        # suffix), never the stored side's different suffix or the stem.
        stored_words = ["kitoblarni", "talabalarga", "maktablarda",
                        "universitetlarning", "mashqlarini", "darslarimizda"]
        checked_words = ["kitoblardan", "talabalardan", "maktablardan",
                         "universitetlardan", "mashqlaridan", "darslarimizdan"]
        stored_text = " ".join(stored_words)
        checked_text = " ".join(checked_words) + " Qoshimcha mustaqil xulosa qismi bu yerda yozilgan."
        stored = self.add(stored_text, "morph-" + uuid.uuid4().hex[:8])
        body, kind = multipart([("document", "t.txt", checked_text.encode())])

        v3_result = self.payload(self.request(body, kind, include_corpus=True, normalization="v3"))
        v3_source = next((s for s in v3_result["sources"] if s.get("corpus", {}).get("id") == stored["id"]), None)
        self.assertIsNotNone(v3_source)  # retrieval found it
        self.assertEqual(v3_source["matches"], [])  # but v2 matching never flags a suffix-only variant
        self.assertEqual(v3_result["coverage_percent"], 0.0)

        body2, kind2 = multipart([("document", "t.txt", checked_text.encode())])
        matching_result = self.payload(self.request(body2, kind2, include_corpus=True,
                                                     normalization="v3-matching"))
        self.assertEqual(matching_result["parameters"]["algorithm_version"], "lexical-shingle-v2")
        self.assertEqual(matching_result["parameters"]["normalization_version"], "uz-latin-v3")
        self.assertEqual(matching_result["corpus"]["normalization"], "v3-matching")
        matching_source = next(s for s in matching_result["sources"] if s.get("corpus", {}).get("id") == stored["id"])
        self.assertTrue(matching_source["matches"])
        match = matching_source["matches"][0]
        # Highlighted text is the full original CHECKED-side word (with its
        # own suffix), read back from the document's own original text.
        self.assertEqual(checked_text[match["document"]["start"]:match["document"]["end"]],
                         match["document"]["text"])
        for word in checked_words:
            self.assertIn(word, match["document"]["text"])
        self.assertGreater(matching_result["coverage_percent"], 0.0)
        self.assertTrue(any("v3 + matching" in line or "uz-latin-v3 + matching" in line
                            for line in matching_result["limitations"]))

    def test_same_idempotency_key_with_different_normalization_conflicts_rather_than_silently_reusing(self):
        self.add(self.unique(UZ), "norm-conflict-" + uuid.uuid4().hex[:8])
        key = str(uuid.uuid4())
        body, kind = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UNRELATED.encode())])
        first = self.request(body, kind, include_corpus=True, normalization="v2", idempotency_key=key)
        self.assertEqual(first.status_code, 200)
        body2, kind2 = multipart([("document", "t.txt", UZ.encode()), ("sources", "s.txt", UNRELATED.encode())])
        with self.assertRaises(persistence.ServiceError) as raised:
            self.request(body2, kind2, include_corpus=True, normalization="v3", idempotency_key=key)
        self.assertEqual((raised.exception.status, raised.exception.code), (409, "request_conflict"))

    def test_non_admin_response_never_carries_full_corpus_text(self):
        filler = " ".join(f"toldiruvchi{i} jumla matni" for i in range(120))
        secret = "MAXFIYKORPUSJUMLASI faqat korpusda turadi va javobga chiqmasligi kerak"
        self.add(f"{UZ} {filler} {secret}", "leak-" + uuid.uuid4().hex[:8])
        body, kind = multipart([("document", "t.txt", UZ.encode()),
                                ("sources", "s.txt", UNRELATED.encode())])
        response = self.request(body, kind, include_corpus=True)
        raw = bytes(response.body).decode("utf-8")
        result = json.loads(raw)
        source = next(s for s in result["sources"] if s.get("corpus"))
        self.assertNotIn("text", source)
        self.assertNotIn("segments", source)
        self.assertTrue(source["text_withheld"])
        for match in source["matches"]:
            excerpt = match["source"]["excerpt"]
            self.assertLessEqual(len(excerpt["before"]), corpus.CORPUS_CONTEXT_CHARS)
            self.assertLessEqual(len(excerpt["after"]), corpus.CORPUS_CONTEXT_CHARS)
        self.assertEqual(result["excerpt_policy"]["context_chars"], corpus.CORPUS_CONTEXT_CHARS)
        # Corpus text away from the matched passage must never be returned.
        self.assertNotIn("MAXFIYKORPUSJUMLASI", raw)
        self.assertNotIn("toldiruvchi60", raw)

    def test_metadata_only_source_withholds_every_excerpt_but_still_counts_coverage(self):
        # A base sentence sharing no vocabulary with UZ/RU/EN/UNRELATED, so this
        # document never becomes a retrieval candidate for another test's
        # plain-UZ query (and vice versa) -- the source is also picked out by
        # its own stored id below, not just "the first corpus source", in case
        # retrieval ever does return more than one candidate.
        base = self.unique("Kompyuter tizimlarida malumotlar bazasini loyihalashtirish "
                            "asoslari keng yoritilgan va amaliy misollar orqali tushuntirilgan")
        filler = " ".join(f"metaonlytoldiruvchi{i} jumla matni" for i in range(120))
        secret = "METAONLYMAXFIYKORPUSJUMLASI faqat korpusda turadi va javobga chiqmasligi kerak"
        stored = self.add(f"{base} {filler} {secret}", "metaonly-" + uuid.uuid4().hex[:8],
                          visibility="metadata_only")
        document = base + " Qoshimcha mustaqil xulosa qismi bu yerda yozilgan."
        body, kind = multipart([("document", "t.txt", document.encode()),
                                ("sources", "s.txt", UNRELATED.encode())])
        response = self.request(body, kind, include_corpus=True)
        raw = bytes(response.body).decode("utf-8")
        result = self.payload(response)
        corpus_sources = [s for s in result["sources"] if s.get("corpus")]
        source = next(s for s in corpus_sources if s["corpus"]["id"] == stored["id"])
        self.assertNotIn("text", source)
        self.assertNotIn("segments", source)
        self.assertTrue(source["text_withheld"])
        self.assertTrue(source["restricted"])
        self.assertEqual(source["restriction_reason"], corpus.RESTRICTED_REASON)
        self.assertTrue(source["matches"])  # moslik topiladi
        for match in source["matches"]:
            self.assertNotIn("text", match["source"])
            self.assertNotIn("excerpt", match["source"])
        self.assertGreater(source["coverage_percent"], 0)  # foizga kiradi
        self.assertGreater(result["coverage_percent"], 0)
        # Not even the matched passage itself may leak, unlike a plain excerpt source.
        self.assertNotIn("METAONLYMAXFIYKORPUSJUMLASI", raw)
        self.assertNotIn("metaonlytoldiruvchi60", raw)

    def test_personal_report_text_never_reaches_the_corpus(self):
        before = corpus.list_documents(1, "all")["items"]
        secret = "Shaxsiy hisobot matni " + uuid.uuid4().hex + " korpusga tushmasligi kerak albatta"
        body, kind = multipart([("document", "p.txt", secret.encode()),
                                ("sources", "q.txt", secret.encode())])
        for flag in (False, True):
            with self.subTest(include_corpus=flag):
                self.payload(self.request(body, kind, include_corpus=flag))
        after = corpus.list_documents(1, "all")["items"]
        self.assertEqual([i["id"] for i in before], [i["id"] for i in after])
        with persistence.database(self.admin) as conn:
            hit = conn.execute("SELECT count(*) AS n FROM antiplagiat.corpus_chunks"
                               " WHERE chunk_text LIKE %s", ("%" + secret[:40] + "%",)).fetchone()["n"]
            docs = conn.execute("SELECT count(*) AS n FROM antiplagiat.corpus_documents"
                                " WHERE extracted_text LIKE %s", ("%" + secret[:40] + "%",)).fetchone()["n"]
        self.assertEqual((hit, docs), (0, 0))


class CorpusAccessTests(CorpusFixture, unittest.TestCase):
    def scope(self, method, path, query=b""):
        return {"type": "http", "method": method, "scheme": "http", "path": path,
                "query_string": query, "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 10),
                "headers": [(b"x-antiplagiat-local", b"1")]}

    def test_listing_requires_an_admin_session(self):
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.user_id), "role": "user"}):
            with self.assertRaises(persistence.ServiceError) as raised:
                corpus_api.listing(Request(self.scope("GET", "/corpus/documents")))
        self.assertEqual(raised.exception.status, 403)
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.admin_id), "role": "admin"}):
            response = corpus_api.listing(Request(self.scope("GET", "/corpus/documents")))
        self.assertEqual(response.status_code, 200)

    def test_withdraw_requires_an_admin_session(self):
        stored = self.add(self.unique(EN + " ruxsat"), "acl-" + uuid.uuid4().hex[:8])
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.user_id), "role": "user"}):
            with self.assertRaises(persistence.ServiceError) as raised:
                corpus_api.withdraw(Request(self.scope("POST", "/corpus/documents")), stored["id"])
        self.assertEqual(raised.exception.status, 403)
        self.assertIsNotNone(corpus.load_for_comparison(stored["id"]))

    def test_anonymous_corpus_access_is_unauthenticated(self):
        with self.assertRaises(persistence.ServiceError) as raised:
            corpus_api.listing(Request(self.scope("GET", "/corpus/documents")))
        self.assertEqual(raised.exception.status, 401)

    def test_unknown_identifier_is_not_found_rather_than_a_driver_error(self):
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.admin_id), "role": "admin"}):
            for identifier in ("not-a-uuid", str(uuid.uuid4())):
                with self.subTest(identifier=identifier), self.assertRaises(corpus.CorpusError) as raised:
                    corpus_api.withdraw(Request(self.scope("POST", "/corpus/documents")), identifier)
                self.assertEqual(raised.exception.status, 404)

    def test_corpus_manager_role_has_the_same_access_as_admin(self):
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.manager_id), "role": "corpus_manager"}):
            response = corpus_api.listing(Request(self.scope("GET", "/corpus/documents")))
            self.assertEqual(response.status_code, 200)
            stored = self.add(self.unique(UZ + " manager"), "mgr-" + uuid.uuid4().hex[:8])
            removed = corpus_api.withdraw(Request(self.scope("POST", "/corpus/documents")), stored["id"])
        self.assertEqual(json.loads(bytes(removed.body))["status"], "withdrawn")

    def test_reviewer_role_is_refused_like_an_ordinary_user(self):
        with patch.object(corpus_api.auth, "require_user",
                          return_value={"id": str(self.reviewer_id), "role": "reviewer"}):
            with self.assertRaises(persistence.ServiceError) as raised:
                corpus_api.listing(Request(self.scope("GET", "/corpus/documents")))
        self.assertEqual(raised.exception.status, 403)


if __name__ == "__main__":
    unittest.main()
