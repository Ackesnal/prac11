"""WSGI endpoints: IAM-protected Cloud Run API with a static demonstration UI."""
import json
import os
from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
import uuid

from agent import run_task, validate_request

ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def services():
    from cloud import Vertex
    from retrieval import Retriever
    provider = Vertex()
    return provider, Retriever(ROOT / "index", provider, ROOT / "knowledge")


def application(environ, start_response):
    path, method = environ.get("PATH_INFO"), environ.get("REQUEST_METHOD")
    code, mime = 200, "application/json; charset=utf-8"
    if path == "/" and method == "GET":
        encoded = (ROOT / "static" / "index.html").read_bytes()
        mime = "text/html; charset=utf-8"
    else:
        data = {}
        try:
            # Cloud Run reserves some paths ending in z; use /health externally.
            if path == "/health" and method == "GET":
                _, retriever = services()
                data = {"status": "index_ready", "chunks": len(retriever.chunks),
                        "corpus_sha256": retriever.manifest["corpus_sha256"],
                        "note": "Index loaded; this does not test live model access."}
            elif path == "/ask" and method == "POST":
                try:
                    length = int(environ.get("CONTENT_LENGTH") or "0")
                    if not 1 <= length <= 16384:
                        raise ValueError("Request body must be 1..16384 bytes")
                    body = json.loads(environ["wsgi.input"].read(length))
                    if not isinstance(body, dict) or not set(body) <= {"question", "mode", "top_k", "min_score"}:
                        raise ValueError("Unexpected request fields")
                    args = {"question": body.get("question"), "mode": body.get("mode", "agent"),
                            "top_k": body.get("top_k", int(os.getenv("TOP_K", "3"))),
                            "min_score": body.get("min_score", float(os.getenv("MIN_SCORE", "0.25")))}
                    validate_request(**args)
                except (ValueError, TypeError, UnicodeError):
                    code, data = 400, {"status": "bad_request", "answer": "Invalid JSON or request parameters."}
                else:
                    provider, retriever = services()
                    data = run_task(provider=provider, retriever=retriever, **args)
                    if data["status"] == "upstream_failure":
                        code = 502
            else:
                code, data = 404, {"status": "not_found"}
        except Exception:
            code, data = 503, {"status": "not_ready", "answer": "Check configuration and rebuild the matching index."}
        data.update(request_id=str(uuid.uuid4()), model=os.getenv("MODEL_ID", "not_configured"),
                    revision=os.getenv("K_REVISION", "local"))
        print(json.dumps({k: data[k] for k in ("request_id", "status", "revision", "elapsed_s",
            "model_calls", "embedding_calls", "tool_calls") if k in data}), flush=True)
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
    start_response(f"{code} {HTTPStatus(code).phrase}", [("Content-Type", mime),
        ("Content-Length", str(len(encoded))), ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff")])
    return [encoded]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server
    with make_server("127.0.0.1", int(os.getenv("PORT", "8080")), application) as server:
        server.serve_forever()
