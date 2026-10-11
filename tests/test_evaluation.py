import unittest
from evaluate import diagnose


class EvaluationTests(unittest.TestCase):
    def test_recall_partial_and_missing_citation_are_separate(self):
        case = {"id":"two", "required_ids":["a","b"], "expected_statuses":["answered"], "keywords":["code"]}
        response = {"status":"answered", "answer":"code", "retrieved":[{"id":"a"}], "sources":[]}
        result = diagnose(case, response)
        self.assertEqual(result["retrieval_recall"], .5)
        self.assertFalse(result["required_sources_cited"])
        self.assertTrue(result["keyword_check"])
        self.assertEqual(result["manual_claim_support"], "TO REVIEW")

    def test_unknown_case_does_not_inflate_retrieval_score(self):
        case = {"id":"unknown", "required_ids":[], "expected_statuses":["insufficient_evidence"], "keywords":[]}
        result = diagnose(case, {"status":"insufficient_evidence"})
        self.assertEqual(result["retrieval_recall"], "N/A")
        self.assertTrue(result["status_expected"])
