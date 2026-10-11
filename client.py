"""Call an authenticated Cloud Run URL, or the local authenticated gcloud proxy."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def request(payload=None, health=False):
    url = os.getenv("SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme != "https" and not local:
        raise ValueError("Use HTTPS, or the loopback proxy URL")
    headers = {"Content-Type": "application/json"}
    if not local:
        token = os.getenv("ID_TOKEN")
        if not token:
            raise ValueError("Set ID_TOKEN from gcloud auth print-identity-token")
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url + ("/healthz" if health else "/ask"), headers=headers,
        data=None if health else json.dumps(payload).encode(), method="GET" if health else "POST")
    try:
        with urllib.request.urlopen(req, timeout=150) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # The app's JSON error response is useful for evaluation; IAM errors may be HTML.
        raw = exc.read(16384)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise RuntimeError(f"HTTP {exc.code}; check caller IAM and token") from None
        result["http_status"] = exc.code
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question")
    parser.add_argument("--mode", choices=["agent", "rag", "plain", "retrieve"], default="agent")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.25)
    parser.add_argument("--health", action="store_true")
    args = parser.parse_args()
    if not args.health and not args.question:
        parser.error("Supply --question or --health")
    try:
        result = request({"question": args.question, "mode": args.mode,
                          "top_k": args.top_k, "min_score": args.min_score}, args.health)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result.get("http_status") or result["status"] in {"upstream_failure", "not_ready"} else 0
    except Exception as exc:
        print(f"Request failed: {type(exc).__name__}. Check URL, identity and service status.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
