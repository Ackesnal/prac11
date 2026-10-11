import os
import unittest
from unittest.mock import patch
from cloud import Vertex


class CloudContractTests(unittest.TestCase):
    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "teaching-project", "EMBEDDING_DIM": "3"})
    def test_document_and_query_tasks_and_dimension_are_sent(self):
        provider = Vertex()
        with patch.object(provider, "post", return_value={"predictions":[{"embeddings":{"values":[1,2,3]}}]}) as post:
            for task in ("RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"):
                provider.embed("hello", task)
                body = post.call_args.args[3]
                self.assertEqual(body["instances"], [{"content":"hello", "task_type":task}])
                self.assertEqual(body["parameters"], {"autoTruncate":False, "outputDimensionality":3})

    @patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "teaching-project"})
    def test_planning_forces_tool_and_answer_requests_json(self):
        provider = Vertex()
        with patch.object(provider, "post", return_value={}) as post:
            provider.generate([], "system", "plan", {"name":"search_course_notes"})
            self.assertEqual(post.call_args.args[3]["toolConfig"]["functionCallingConfig"]["mode"], "ANY")
            provider.generate([], "system", "answer")
            self.assertNotIn("tools", post.call_args.args[3])
            self.assertEqual(post.call_args.args[3]["generationConfig"]["responseMimeType"], "application/json")


if __name__ == "__main__":
    unittest.main()
