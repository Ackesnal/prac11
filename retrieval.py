"""Versioned, read-only FAISS corpus. Index construction is a separate CLI step."""
import hashlib
import json
from pathlib import Path

import faiss
import numpy as np


def corpus_hash(folder):
    files = sorted(Path(folder).glob("*.md"))
    if not files:
        raise ValueError("The knowledge directory contains no Markdown files")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def chunks_from(folder, size=120, overlap=25):
    """Paragraph-aware windows, measured in whitespace-separated words (not tokens)."""
    if not 20 <= size <= 300 or not 0 <= overlap < size:
        raise ValueError("Use chunk size 20..300 and overlap 0..size-1")
    chunks = []
    for path in sorted(Path(folder).glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ")
        number = 0
        for paragraph in text.split("\n\n"):
            if not paragraph.strip() or paragraph.strip().startswith("#"):
                continue
            words = paragraph.split()
            for start in range(0, len(words), size - overlap):
                number += 1
                chunk = " ".join(words[start:start + size])
                chunks.append({"id": f"{path.stem}-{number:02d}", "source": path.name,
                               "title": title, "text": chunk})
                if start + size >= len(words):
                    break
    if not chunks:
        raise ValueError("Knowledge files contain no body paragraphs")
    return chunks


def normalised(values, dimension):
    matrix = np.asarray(values, dtype="float32")
    if matrix.ndim != 2 or matrix.shape[1] != dimension or not np.isfinite(matrix).all():
        raise ValueError("Invalid embedding shape or non-finite values")
    if np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise ValueError("Zero embedding vector")
    matrix = np.ascontiguousarray(matrix)
    faiss.normalize_L2(matrix)
    return matrix


def build_index(knowledge, destination, provider, size=120, overlap=25):
    chunks = chunks_from(knowledge, size, overlap)
    # One text per request is required by gemini-embedding-001.
    vectors = [provider.embed(c["text"], "RETRIEVAL_DOCUMENT") for c in chunks]
    index = faiss.IndexFlatIP(provider.dimension)
    index.add(normalised(vectors, provider.dimension))
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(dest / "index.faiss"))
    metadata = {"schema_version": 1, "embedding_model": provider.embedding_model,
        "embedding_location": provider.embedding_location, "dimension": provider.dimension,
        "metric": "cosine_via_normalised_inner_product", "chunk_words": size,
        "overlap_words": overlap, "corpus_sha256": corpus_hash(knowledge), "chunks": chunks}
    # Metadata hashes detect accidental index replacement. This is not a signature.
    metadata["index_sha256"] = hashlib.sha256((dest / "index.faiss").read_bytes()).hexdigest()
    (dest / "manifest.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return metadata


class Retriever:
    def __init__(self, directory, provider, knowledge=None):
        directory = Path(directory)
        self.manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        m = self.manifest
        if (m["embedding_model"], m["embedding_location"], m["dimension"]) != (
            provider.embedding_model, provider.embedding_location, provider.dimension):
            raise ValueError("Embedding configuration changed. Rebuild the index before deploying.")
        if knowledge and corpus_hash(knowledge) != m["corpus_sha256"]:
            raise ValueError("Knowledge changed. Rebuild the index before deploying.")
        if hashlib.sha256((directory / "index.faiss").read_bytes()).hexdigest() != m["index_sha256"]:
            raise ValueError("Index checksum mismatch")
        self.index = faiss.read_index(str(directory / "index.faiss"))
        self.chunks = m["chunks"]
        if self.index.d != provider.dimension or self.index.ntotal != len(self.chunks):
            raise ValueError("Index and manifest disagree")
        self.provider = provider

    def search(self, query, top_k=3, min_score=0.25):
        vector = self.provider.embed(query, "RETRIEVAL_QUERY")
        scores, rows = self.index.search(normalised([vector], self.index.d), min(top_k, self.index.ntotal))
        return [dict(self.chunks[int(row)], score=round(float(score), 4))
                for score, row in zip(scores[0], rows[0]) if row >= 0 and float(score) >= min_score]
