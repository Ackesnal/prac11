import copy
import io
import json
import unittest
from unittest.mock import patch

import agent
import app


def reply(parts, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"role": "model", "parts": parts}}]}


def proposal(query="A1 submission code deadline", name="search_course_notes", **extra):
    return {"functionCall": {"name": name, "args": {"query": query, **extra}, "id": "call-1"},
            "thoughtSignature": "PRIVATE_SIGNATURE"}


def answer(ids=None, text=None, insufficient=False):
    ids = ["assessment-01"] if ids is None else ids
    return reply([{"text": json.dumps({"answer": text or "ORCHID-742 [assessment-01]",
        "source_ids": ids, "insufficient_evidence": insufficient})}])


class Provider:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.history = []

    def generate(self, contents, system, phase, declaration):
        self.history.append(copy.deepcopy(contents))
        return next(self.replies)


class Search:
    manifest = {"corpus_sha256": "test-corpus"}

    def __init__(self, empty=False):
        self.empty = empty
        self.calls = []

    def search(self, query, top_k, min_score):
        self.calls.append((query, top_k, min_score))
        return [] if self.empty else [{"id": "assessment-01", "text": "Fictional A1 code ORCHID-742.",
                                      "source": "assessment.md", "score": 0.8}]


class AgentTests(unittest.TestCase):
    def test_agent_preserves_private_signature_and_call_id(self):
        provider = Provider([reply([proposal()]), answer()])
        result = agent.run_task("A1?", provider, Search())
        self.assertEqual(result["status"], "answered")
        self.assertEqual((result["model_calls"], result["embedding_calls"], result["tool_calls"]), (2, 1, 1))
        self.assertEqual(provider.history[1][1]["parts"][0]["thoughtSignature"], "PRIVATE_SIGNATURE")
        self.assertEqual(provider.history[1][2]["parts"][0]["functionResponse"]["id"], "call-1")
        self.assertNotIn("PRIVATE_SIGNATURE", json.dumps(result))

    def test_plain_uses_no_retrieval(self):
        search = Search()
        result = agent.run_task("A1?", Provider([reply([{"text": "Unknown"}])]), search, mode="plain")
        self.assertEqual(result["status"], "baseline_unverified")
        self.assertEqual(search.calls, [])

    def test_fixed_rag_uses_original_question(self):
        search = Search()
        result = agent.run_task("exact question", Provider([answer()]), search, mode="rag")
        self.assertEqual(search.calls[0][0], "exact question")
        self.assertEqual(result["model_calls"], 1)

    def test_empty_retrieval_stops_before_answer_call(self):
        result = agent.run_task("missing", Provider([reply([proposal()])]), Search(True))
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["model_calls"], 1)

    def test_unknown_fact_model_abstention_replaces_generated_text(self):
        result = agent.run_task("A99?", Provider([answer(text="untrusted invented date", insufficient=True)]), Search(), mode="rag")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertNotIn("invented date", result["answer"])

    def test_invalid_or_multiple_proposals_never_execute(self):
        for parts in ([proposal(name="delete_files")], [proposal(admin=True)],
                      [proposal(query=23)], [proposal(), proposal()], [{"text": "Skipped tool"}]):
            with self.subTest(parts=parts):
                search = Search()
                result = agent.run_task("A1?", Provider([reply(parts)]), search)
                self.assertEqual(result["status"], "policy_denied")
                self.assertEqual(search.calls, [])

    def test_repeated_call_denied(self):
        result = agent.run_task("A1?", Provider([reply([proposal()]), reply([proposal()])]), Search())
        self.assertEqual(result["status"], "policy_denied")
        self.assertEqual(result["tool_calls"], 1)

    def test_missing_fabricated_or_unlisted_inline_citations_rejected(self):
        for ids, text in [([], "No citation"), (["fake-01"], "Invented [fake-01]"),
                          (["assessment-01"], "Wrong [fake-01]"), (["assessment-01"], "No brackets")]:
            result = agent.run_task("A1?", Provider([answer(ids, text)]), Search(), mode="rag")
            self.assertEqual(result["status"], "citation_rejected")

    def test_incomplete_model_and_invalid_json_fail_closed(self):
        for response in [reply([{"text": "partial"}], "MAX_TOKENS"),
                         {"candidates": []}, reply([{"text": "not json"}])]:
            result = agent.run_task("A1?", Provider([response]), Search(), mode="rag")
            self.assertEqual(result["status"], "upstream_failure")

    def test_bad_parameters_do_not_call_provider(self):
        for fields in [{"top_k": True}, {"top_k": 6}, {"min_score": float('nan')},
                       {"mode": []}, {"question": " "}]:
            args = dict(question="A1?", mode="agent", top_k=3, min_score=.25)
            args.update(fields)
            with self.assertRaises(ValueError):
                agent.run_task(provider=Provider([]), retriever=Search(), **args)

    def test_http_invalid_payloads_rejected_before_loading_services(self):
        for payload in [b'[]', b'{"question":"A1?","top_k":true}', b'{"question":3}', b'not json']:
            env = {"PATH_INFO": "/ask", "REQUEST_METHOD": "POST", "CONTENT_LENGTH": str(len(payload)), "wsgi.input": io.BytesIO(payload)}
            status = []
            with patch("app.services") as services:
                raw = b''.join(app.application(env, lambda s,h: status.append(s)))
                services.assert_not_called()
            self.assertTrue(status[0].startswith("400"))
            self.assertEqual(json.loads(raw)["status"], "bad_request")


if __name__ == "__main__":
    unittest.main()
