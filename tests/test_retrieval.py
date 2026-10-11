"""Actual FAISS search with synthetic vectors; no cloud quality claims."""
import tempfile
import unittest
from pathlib import Path
from retrieval import Retriever, build_index, chunks_from, normalised


class Embeddings:
    embedding_model = "test-vectors"
    embedding_location = "test-region"
    dimension = 3

    def embed(self, text, task_type):
        return [1, 0, 0] if "apple" in text else [0, 1, 0]


class RetrievalTests(unittest.TestCase):
    def test_saved_index_search_reload_threshold_and_staleness(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            kb = root / "knowledge"
            kb.mkdir()
            (kb / "fruit.md").write_text("# Fruit\n\napple orchard\n\nbanana grove", encoding="utf-8")
            provider = Embeddings()
            build_index(kb, root / "index", provider)
            search = Retriever(root / "index", provider, kb)
            self.assertEqual(search.search("apple", 3, .25)[0]["id"], "fruit-01")
            self.assertEqual(len(search.search("apple", 3, .25)), 1)
            self.assertEqual(len(search.search("apple", 3, -1)), 2)
            provider.dimension = 2
            with self.assertRaises(ValueError):
                Retriever(root / "index", provider)
            provider.dimension = 3
            (kb / "fruit.md").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                Retriever(root / "index", provider, kb)

    def test_overlapping_chunks_cover_all_words(self):
        with tempfile.TemporaryDirectory() as temp:
            words = [str(i) for i in range(55)]
            Path(temp, "one.md").write_text("# Numbers\n\n" + " ".join(words), encoding="utf-8")
            chunks = chunks_from(temp, 20, 5)
            self.assertEqual(chunks[1]["text"].split()[0], "15")
            self.assertEqual(set(" ".join(c["text"] for c in chunks).split()), set(words))

    def test_bad_vectors_rejected(self):
        for values in [[[0,0,0]], [[float('nan'),0,1]], [[1,0]]]:
            with self.assertRaises(ValueError):
                normalised(values, 3)


if __name__ == "__main__":
    unittest.main()
