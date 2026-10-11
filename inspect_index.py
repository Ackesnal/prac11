"""Inspect index metadata or run a retrieval-only query using the same stored vectors."""
import argparse
import json
from cloud import Vertex
from retrieval import Retriever


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", default="index")
    parser.add_argument("--knowledge", default="knowledge")
    parser.add_argument("--query")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=.25)
    parser.add_argument("--gcloud", action="store_true")
    args = parser.parse_args()
    provider = Vertex(use_gcloud=args.gcloud)
    retriever = Retriever(args.index, provider, args.knowledge)
    meta = {k:v for k,v in retriever.manifest.items() if k != "chunks"}
    meta["chunk_count"] = len(retriever.chunks)
    print(json.dumps(meta, indent=2))
    if args.query:
        from agent import validate_request
        validate_request(args.query, "retrieve", args.top_k, args.min_score)
        print(json.dumps(retriever.search(args.query, args.top_k, args.min_score), indent=2))
    else:
        for chunk in retriever.chunks:
            print(chunk["id"], len(chunk["text"].split()), "words:", chunk["text"][:90])


if __name__ == "__main__":
    main()
