"""Corpus unit tests: chunking, query windows, metadata rules, excerpt redaction
and role checks. No database and no network; synthetic text only."""
import unittest
import uuid
from unittest.mock import MagicMock, patch

from backend import auth, corpus
from backend.comparison.matching import tokenize
from backend.persistence import ServiceError
from backend.tests.test_auth import request

WORDS = ["ilmiy", "tadqiqot", "matn", "tahlil", "natija", "jadval", "manba", "xulosa",
         "usul", "tajriba", "mezon", "model"]


def synthetic_text(count):
    return " ".join(WORDS[i % len(WORDS)] + str(i) for i in range(count))


class ChunkingTests(unittest.TestCase):
    def test_chunk_offsets_map_back_to_the_original_text(self):
        text = synthetic_text(130)
        tokens = tokenize(text)
        chunks = corpus.chunk_document(text, tokens)
        self.assertTrue(chunks)
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["chunk_text"])
            self.assertLess(chunk["char_start"], chunk["char_end"])
            self.assertEqual(chunk["token_end"] - chunk["token_start"],
                             len(tokenize(chunk["chunk_text"])))

    def test_chunks_overlap_so_no_shingle_falls_between_them(self):
        text = synthetic_text(200)
        chunks = corpus.chunk_document(text, tokenize(text))
        self.assertGreater(len(chunks), 1)
        step = corpus.CHUNK_TOKENS - corpus.CHUNK_OVERLAP_TOKENS
        for earlier, later in zip(chunks, chunks[1:]):
            self.assertEqual(later["token_start"] - earlier["token_start"], step)
            self.assertGreater(earlier["token_end"], later["token_start"])
            self.assertGreaterEqual(earlier["token_end"] - later["token_start"],
                                    corpus.CHUNK_OVERLAP_TOKENS)

    def test_every_token_appears_in_at_least_one_chunk(self):
        text = synthetic_text(95)
        tokens = tokenize(text)
        chunks = corpus.chunk_document(text, tokens)
        covered = {i for c in chunks for i in range(c["token_start"], c["token_end"])}
        self.assertEqual(covered, set(range(len(tokens))))

    def test_short_document_becomes_one_chunk(self):
        text = synthetic_text(6)
        chunks = corpus.chunk_document(text, tokenize(text))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_text"], text)


class QueryWindowTests(unittest.TestCase):
    def test_short_document_yields_one_window(self):
        tokens = tokenize(synthetic_text(10))
        self.assertEqual(len(corpus.query_windows(tokens)), 1)

    def test_long_document_is_sampled_within_the_bound(self):
        tokens = tokenize(synthetic_text(4000))
        windows = corpus.query_windows(tokens)
        self.assertLessEqual(len(windows), corpus.MAX_QUERY_WINDOWS)
        self.assertTrue(all(w.strip() for w in windows))
        for window in windows:
            self.assertLessEqual(len(window.split()), corpus.QUERY_WINDOW_TOKENS)

    def test_windows_reach_both_ends_of_the_document(self):
        tokens = tokenize(synthetic_text(2000))
        windows = corpus.query_windows(tokens)
        self.assertIn(tokens[0]["value"], windows[0].split())
        self.assertIn(tokens[-1]["value"], windows[-1].split())


class MetadataTests(unittest.TestCase):
    def valid(self):
        return {"title": "Sinov hujjati", "author_display": "Sinov Muallif", "doc_type": "bmi",
                "year": 2024, "language_hint": "uz", "source_note": "",
                "permission_basis": "Akademiya ruxsati 2024/01", "original_filename": "a.txt"}

    def test_valid_metadata_has_no_problems(self):
        self.assertEqual(corpus.metadata_errors(self.valid()), [])

    def test_permission_basis_is_mandatory(self):
        for value in ("", "   "):
            with self.subTest(value=value):
                broken = {**self.valid(), "permission_basis": value}
                self.assertTrue(any("Ruxsat asosi" in p for p in corpus.metadata_errors(broken)))

    def test_title_type_and_year_are_validated(self):
        for field, value, marker in [("title", "  ", "Sarlavha"), ("doc_type", "kitob", "turi"),
                                     ("year", 1500, "Yil"), ("year", "2024", "Yil"),
                                     ("title", "x" * 301, "title")]:
            with self.subTest(field=field, value=value):
                problems = corpus.metadata_errors({**self.valid(), field: value})
                self.assertTrue(any(marker in p for p in problems), problems)

    def test_add_document_refuses_metadata_before_touching_the_database(self):
        with patch.object(corpus, "database") as never:
            with self.assertRaises(corpus.CorpusError) as raised:
                corpus.add_document({**self.valid(), "permission_basis": ""},
                                    {"text": synthetic_text(50), "segments": []}, uuid.uuid4(), b"x")
            self.assertEqual(raised.exception.status, 400)
            never.assert_not_called()


class RedactionTests(unittest.TestCase):
    def report(self, corpus_text, match_text, start):
        return {"sources": [
            {"name": "qo‘lda yuklangan", "text": "qo‘lda yuklangan to‘liq matn", "matches": []},
            {"name": "Korpus hujjati", "text": corpus_text, "segments": [{"kind": "paragraph"}],
             "corpus": {"id": "x", "title": "Korpus hujjati"},
             "matches": [{"method": "shingle",
                          "document": {"start": 0, "end": 5, "text": "boshqa"},
                          "source": {"start": start, "end": start + len(match_text),
                                     "text": match_text}}]}]}

    def test_corpus_text_is_removed_and_context_is_bounded(self):
        body = "A" * 1000 + "MOSPARCHA" + "B" * 1000
        result = corpus.redact(self.report(body, "MOSPARCHA", 1000))
        manual, source = result["sources"]
        self.assertEqual(manual["text"], "qo‘lda yuklangan to‘liq matn")
        self.assertNotIn("text", source)
        self.assertNotIn("segments", source)
        self.assertTrue(source["text_withheld"])
        excerpt = source["matches"][0]["source"]["excerpt"]
        self.assertEqual(len(excerpt["before"]), corpus.CORPUS_CONTEXT_CHARS)
        self.assertEqual(len(excerpt["after"]), corpus.CORPUS_CONTEXT_CHARS)
        self.assertNotIn("A" * 300, excerpt["before"])
        joined = excerpt["before"] + source["matches"][0]["source"]["text"] + excerpt["after"]
        self.assertNotIn(body, joined)

    def test_long_match_text_is_truncated(self):
        match = "M" * (corpus.CORPUS_MATCH_CHARS + 500)
        result = corpus.redact(self.report("x" + match + "y", match, 1))
        side = result["sources"][1]["matches"][0]["source"]
        self.assertEqual(len(side["text"]), corpus.CORPUS_MATCH_CHARS)
        self.assertTrue(side["match_truncated"])

    def test_report_wide_context_budget_is_enforced(self):
        body = "C" * 200_000
        matches = [{"method": "shingle", "document": {"start": 0, "end": 5, "text": "d"},
                    "source": {"start": 900 * i + 10, "end": 900 * i + 20, "text": "C" * 10}}
                   for i in range(200)]
        report = {"sources": [{"name": "K", "text": body, "corpus": {"id": "x"}, "matches": matches}]}
        result = corpus.redact(report)
        shown = result["sources"][0]["matches"]
        context = sum(len(m["source"]["excerpt"]["before"]) + len(m["source"]["excerpt"]["after"])
                      for m in shown)
        self.assertLessEqual(context, corpus.CORPUS_EXCERPT_BUDGET)
        self.assertLess(context, len(body) // 4)
        # Once the budget is spent, later matches carry no unseen corpus text.
        self.assertEqual(shown[-1]["source"]["excerpt"], {"before": "", "after": ""})
        self.assertEqual(result["excerpt_policy"]["context_chars"], corpus.CORPUS_CONTEXT_CHARS)


class RoleTests(unittest.TestCase):
    def signed_in(self, role):
        return patch.object(auth, "require_user", return_value={"id": "u", "username": "t", "role": role})

    def test_admin_passes_and_non_management_roles_are_refused(self):
        with self.signed_in("admin"):
            self.assertEqual(auth.require_corpus_manager(request())["role"], "admin")
        for role in ("user", "reviewer"):
            with self.subTest(role=role), self.signed_in(role):
                with self.assertRaises(ServiceError) as raised:
                    auth.require_corpus_manager(request())
                self.assertEqual(raised.exception.status, 403)

    def test_corpus_manager_role_is_also_accepted(self):
        with self.signed_in("corpus_manager"):
            self.assertEqual(auth.require_corpus_manager(request())["role"], "corpus_manager")

    def test_anonymous_request_is_unauthenticated_not_forbidden(self):
        with self.assertRaises(ServiceError) as raised:
            auth.require_corpus_manager(request())
        self.assertEqual(raised.exception.status, 401)


class RetrievalContractTests(unittest.TestCase):
    def test_candidate_limit_is_clamped_and_rank_is_not_a_percentage(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [
            {"id": uuid.uuid4(), "total_rank": 0.42, "matched_chunks": 3}]
        with patch.object(corpus, "database") as db:
            db.return_value.__enter__.return_value = conn
            found, limit = corpus.candidates(tokenize(synthetic_text(60)), limit=999)
        self.assertEqual(limit, corpus.MAX_CANDIDATES)
        self.assertEqual(len(found), 1)
        self.assertIn("retrieval_rank", found[0])
        self.assertNotIn("coverage_percent", found[0])
        self.assertNotIn("similarity", found[0])

    def test_retrieval_sets_its_own_statement_timeout(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = []
        with patch.object(corpus, "database") as db:
            db.return_value.__enter__.return_value = conn
            corpus.candidates(tokenize(synthetic_text(60)))
        first = conn.execute.call_args_list[0].args[0]
        self.assertIn("SET LOCAL statement_timeout", first)
        self.assertIn(str(corpus.RETRIEVAL_TIMEOUT_MS), first)


if __name__ == "__main__":
    unittest.main()
