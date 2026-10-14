"""Unit tests for backend.benchmark.metrics: every expected value here is
hand-computed in the test itself (in a comment), not derived from the code
under test. No database, no files, no randomness."""
import unittest

from backend.benchmark import metrics


class RetrievalMetricsTests(unittest.TestCase):
    def test_recall_at_k_hand_computed(self):
        ranked = ["c", "a", "x", "b", "y"]
        expected = {"a", "b", "z"}
        # top-1 = {c}: 0 of {a,b,z} found -> 0/3
        self.assertEqual(metrics.recall_at_k(ranked, expected, 1), 0.0)
        # top-3 = {c,a,x}: {a} found -> 1/3
        self.assertAlmostEqual(metrics.recall_at_k(ranked, expected, 3), 1 / 3)
        # top-5 = all ranked: {a,b} found, z never appears -> 2/3
        self.assertAlmostEqual(metrics.recall_at_k(ranked, expected, 5), 2 / 3)

    def test_recall_at_k_undefined_for_no_expected(self):
        self.assertIsNone(metrics.recall_at_k(["a", "b"], set(), 5))
        self.assertIsNone(metrics.recall_at_k(["a", "b"], [], 5))

    def test_precision_at_k_hand_computed(self):
        ranked = ["a", "x", "b", "y", "z"]
        expected = {"a", "b"}
        # top-1 = {a}: 1 relevant of 1 -> 1.0
        self.assertEqual(metrics.precision_at_k(ranked, expected, 1), 1.0)
        # top-3 = {a,x,b}: 2 relevant of 3 -> 2/3
        self.assertAlmostEqual(metrics.precision_at_k(ranked, expected, 3), 2 / 3)
        # top-10 but only 5 ranked: divides by actual 5, not 10 -> 2/5
        self.assertAlmostEqual(metrics.precision_at_k(ranked, expected, 10), 2 / 5)

    def test_precision_at_k_undefined_when_nothing_retrieved(self):
        self.assertIsNone(metrics.precision_at_k([], {"a"}, 5))

    def test_reciprocal_rank_hand_computed(self):
        # first relevant id ("b") is at 1-based rank 3 -> 1/3
        self.assertAlmostEqual(metrics.reciprocal_rank(["x", "y", "b", "a"], {"a", "b"}), 1 / 3)
        # relevant id is first -> 1/1
        self.assertEqual(metrics.reciprocal_rank(["a", "x"], {"a"}), 1.0)
        # none of the expected ids ever appear -> 0.0 (not None: there WAS something to find)
        self.assertEqual(metrics.reciprocal_rank(["x", "y"], {"a"}), 0.0)
        # nothing expected -> undefined
        self.assertIsNone(metrics.reciprocal_rank(["x", "y"], set()))

    def test_aggregate_retrieval_hand_computed(self):
        rows = [
            {"ranked_ids": ["a", "x"], "expected_ids": {"a"}},   # recall@1=1, recall@5=1, p@5=1/2, rr=1
            {"ranked_ids": ["x", "y"], "expected_ids": {"a"}},   # recall@1=0, recall@5=0, p@5=0,   rr=0
            {"ranked_ids": ["x"], "expected_ids": set()},        # excluded from recall/MRR; p@5=0/1=0 (not excluded)
        ]
        result = metrics.aggregate_retrieval(rows)
        self.assertAlmostEqual(result["recall_at_1"], 0.5)   # mean(1, 0) over the 2 defined rows
        self.assertEqual(result["recall_at_1_n"], 2)
        self.assertAlmostEqual(result["recall_at_5"], 0.5)
        # precision@5 is defined for all 3 rows: mean(1/2, 0, 0) = 1/6
        self.assertAlmostEqual(result["precision_at_5"], 1 / 6)
        self.assertEqual(result["precision_at_5_n"], 3)
        self.assertAlmostEqual(result["mrr"], 0.5)           # mean(1, 0) over the 2 defined rows
        self.assertEqual(result["mrr_n"], 2)

    def test_aggregate_retrieval_all_negative_queries_gives_none(self):
        rows = [{"ranked_ids": ["x"], "expected_ids": set()} for _ in range(3)]
        result = metrics.aggregate_retrieval(rows)
        self.assertIsNone(result["recall_at_5"])
        self.assertEqual(result["recall_at_5_n"], 0)


class SpanToTokenSetTests(unittest.TestCase):
    def tokens(self):
        # Five tokens at known character offsets, as tokenize() would produce
        # for "ab cd ef gh ij" (2-char words, 1-char spaces):
        # ab[0,2) cd[3,5) ef[6,8) gh[9,11) ij[12,14)
        return [{"start": 0, "end": 2}, {"start": 3, "end": 5}, {"start": 6, "end": 8},
                {"start": 9, "end": 11}, {"start": 12, "end": 14}]

    def test_single_span_covers_only_overlapping_tokens(self):
        # span [3,8) overlaps token 1 (cd, 3-5) and token 2 (ef, 6-8) only.
        self.assertEqual(metrics.span_to_token_set(self.tokens(), [(3, 8)]), {1, 2})

    def test_span_touching_only_boundary_is_excluded(self):
        # span [2,3) touches neither token (end-exclusive on both sides: it
        # sits exactly in the gap between "ab" and "cd").
        self.assertEqual(metrics.span_to_token_set(self.tokens(), [(2, 3)]), set())

    def test_multiple_spans_union(self):
        self.assertEqual(metrics.span_to_token_set(self.tokens(), [(0, 2), (9, 14)]), {0, 3, 4})

    def test_empty_spans_gives_empty_set(self):
        self.assertEqual(metrics.span_to_token_set(self.tokens(), []), set())


class TokenPrf1Tests(unittest.TestCase):
    def test_hand_computed_partial_overlap(self):
        # predicted {1,2,3}, truth {2,3,4}: TP=2, FP=1 (token 1), FN=1 (token 4)
        # precision = 2/3, recall = 2/3, f1 = 2*(2/3*2/3)/(2/3+2/3) = 2/3
        result = metrics.token_prf1({1, 2, 3}, {2, 3, 4})
        self.assertAlmostEqual(result["precision"], 2 / 3)
        self.assertAlmostEqual(result["recall"], 2 / 3)
        self.assertAlmostEqual(result["f1"], 2 / 3)
        self.assertEqual(result["true_positive_tokens"], 2)
        self.assertEqual(result["false_positive_tokens"], 1)

    def test_both_empty_is_a_perfect_negative(self):
        result = metrics.token_prf1(set(), set())
        self.assertEqual(result, {"precision": 1.0, "recall": 1.0, "f1": 1.0,
                                  "false_positive_tokens": 0, "true_positive_tokens": 0})

    def test_false_positive_on_empty_truth(self):
        # Hard-negative category: nothing should have matched, but 2 tokens did.
        result = metrics.token_prf1({5, 6}, set())
        self.assertEqual(result["precision"], 0.0)
        self.assertIsNone(result["recall"])
        self.assertEqual(result["f1"], 0.0)
        self.assertEqual(result["false_positive_tokens"], 2)

    def test_missed_everything_on_nonempty_truth(self):
        result = metrics.token_prf1(set(), {1, 2})
        self.assertIsNone(result["precision"])
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["f1"], 0.0)

    def test_exact_match(self):
        result = metrics.token_prf1({1, 2, 3}, {1, 2, 3})
        self.assertEqual((result["precision"], result["recall"], result["f1"]), (1.0, 1.0, 1.0))


class AggregateMatchingTests(unittest.TestCase):
    def test_macro_average_hand_computed(self):
        rows = [metrics.token_prf1({1, 2}, {1, 2}),       # P=R=F1=1
                metrics.token_prf1(set(), set()),          # P=R=F1=1
                metrics.token_prf1({1}, {1, 2, 3})]         # P=1, R=1/3, F1=2*(1*1/3)/(1+1/3)=0.5
        result = metrics.aggregate_matching(rows)
        self.assertAlmostEqual(result["precision"], 1.0)
        self.assertAlmostEqual(result["recall"], (1 + 1 + 1 / 3) / 3)
        self.assertAlmostEqual(result["f1"], (1 + 1 + 0.5) / 3)
        self.assertEqual(result["f1_n"], 3)
        self.assertEqual(result["false_positive_queries"], 0)

    def test_false_positive_queries_counted(self):
        rows = [metrics.token_prf1({1}, set()), metrics.token_prf1(set(), set())]
        result = metrics.aggregate_matching(rows)
        self.assertEqual(result["false_positive_queries"], 1)


if __name__ == "__main__":
    unittest.main()
