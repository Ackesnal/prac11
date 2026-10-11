"""Generate real Vertex embeddings once, before the container build."""
import argparse
from pathlib import Path
from cloud import Vertex
from retrieval import build_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge", default="knowledge")
    parser.add_argument("--output", default="index")
    parser.add_argument("--chunk-words", type=int, default=120)
    parser.add_argument("--overlap-words", type=int, default=25)
    parser.add_argument("--gcloud", action="store_true", help="Use Cloud Shell's gcloud account")
    args = parser.parse_args()
    provider = Vertex(use_gcloud=args.gcloud)
    m = build_index(args.knowledge, args.output, provider, args.chunk_words, args.overlap_words)
    print(f"Indexed {len(m['chunks'])} chunks into {Path(args.output).resolve()}")
    print(f"Model={m['embedding_model']} dimensions={m['dimension']} corpus={m['corpus_sha256'][:12]}")


if __name__ == "__main__":
    main()
