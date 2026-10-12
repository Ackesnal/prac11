"""Call an authenticated Cloud Run URL, or the local authenticated gcloud proxy."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


class ClientError(RuntimeError):
    """A diagnostic written by this client, without response bodies or credentials."""


def request(payload=None, health=False):
    url = os.getenv("SERVICE_URL", "http://127.0.0.1:8080").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme != "https" and not local:
        raise ClientError("Set SERVICE_URL to HTTPS, or to the loopback proxy URL")
    headers = {"Content-Type": "application/json"}
    if not local:
        token = os.getenv("ID_TOKEN")
        if not token:
            raise ClientError("Set ID_TOKEN from gcloud auth print-identity-token")
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url + ("/health" if health else "/ask"), headers=headers,
        data=None if health else json.dumps(payload).encode(), method="GET" if health else "POST")
    try:
        with urllib.request.urlopen(req, timeout=150) as response:
            result = json.load(response)
            if not isinstance(result, dict) or not isinstance(result.get("status"), str):
                raise ClientError("The response is not the expected application JSON. Check SERVICE_URL.")
            return result
    except urllib.error.HTTPError as exc:
        # The app's JSON error response is useful for evaluation; IAM errors may be HTML.
        raw = exc.read(16384)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            result = None
        if isinstance(result, dict) and isinstance(result.get("status"), str):
            result["http_status"] = exc.code
            return result
        if exc.code in (401, 403):
            hint = "Check the token's account, roles/run.invoker and token expiry."
        elif exc.code == 404:
            hint = ("Check SERVICE_URL and deploy the app with /health. Cloud Run reserves "
                    "some paths ending in z; also check ingress and whether the default URL is enabled.")
        elif exc.code >= 500:
            hint = "Check the ready revision, container startup and Cloud Run logs."
        else:
            hint = "Check the service status and Cloud Run request logs."
        raise ClientError(f"HTTP {exc.code}; no application JSON. {hint}") from None
    except urllib.error.URLError:
        raise ClientError("Connection failed. Check SERVICE_URL, network access and the local proxy if used.") from None
    except TimeoutError:
        raise ClientError("Request timed out. Check service status and logs before retrying.") from None
    except (ValueError, UnicodeError):
        raise ClientError("The response is not valid application JSON. Check SERVICE_URL.") from None


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
    except ClientError as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Request failed: {type(exc).__name__}. Check URL, identity and service status.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
