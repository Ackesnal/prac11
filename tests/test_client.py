"""Client diagnostics and the externally reachable health route; no cloud calls."""
import io
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import app
import client


class ClientTests(unittest.TestCase):
    def test_health_client_and_wsgi_route_agree(self):
        def local_request(request, timeout):
            self.assertEqual(request.full_url, "https://service.example/health")
            statuses = []
            retriever = SimpleNamespace(chunks=[{}], manifest={"corpus_sha256": "test-corpus"})
            with patch("app.services", return_value=(None, retriever)):
                raw = b"".join(app.application({"PATH_INFO": "/health", "REQUEST_METHOD": "GET"},
                                              lambda status, headers: statuses.append(status)))
            self.assertEqual(statuses, ["200 OK"])
            return io.BytesIO(raw)

        with patch.dict(os.environ, SERVICE_URL="https://service.example", ID_TOKEN="secret-token"), \
             patch("client.urllib.request.urlopen", side_effect=local_request):
            self.assertEqual(client.request(health=True)["status"], "index_ready")

    def test_html_errors_keep_http_status_without_leaking_body_or_token(self):
        for status in (401, 403, 404, 503):
            with self.subTest(status=status):
                error = HTTPError("https://service.example/health", status, "error", {},
                                  io.BytesIO(b"<html>secret-token PRIVATE_BODY</html>"))
                output = io.StringIO()
                with patch.dict(os.environ, SERVICE_URL="https://service.example", ID_TOKEN="secret-token"), \
                     patch("client.urllib.request.urlopen", side_effect=error), \
                     patch("sys.argv", ["client.py", "--health"]), patch("sys.stderr", output):
                    self.assertEqual(client.main(), 1)
                diagnostic = output.getvalue()
                self.assertIn(f"HTTP {status}", diagnostic)
                self.assertNotIn("secret-token", diagnostic)
                self.assertNotIn("PRIVATE_BODY", diagnostic)

    def test_application_error_json_is_preserved(self):
        error = HTTPError("https://service.example/health", 503, "error", {},
                          io.BytesIO(json.dumps({"status": "not_ready"}).encode()))
        with patch.dict(os.environ, SERVICE_URL="https://service.example", ID_TOKEN="secret-token"), \
             patch("client.urllib.request.urlopen", side_effect=error):
            self.assertEqual(client.request(health=True), {"status": "not_ready", "http_status": 503})

    def test_unexpected_error_json_keeps_http_status(self):
        error = HTTPError("https://service.example/health", 404, "error", {}, io.BytesIO(b"[]"))
        with patch.dict(os.environ, SERVICE_URL="https://service.example", ID_TOKEN="secret-token"), \
             patch("client.urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(client.ClientError, "HTTP 404"):
                client.request(health=True)

    def test_connection_error_has_safe_diagnostic(self):
        with patch.dict(os.environ, SERVICE_URL="https://service.example", ID_TOKEN="secret-token"), \
             patch("client.urllib.request.urlopen", side_effect=URLError("PRIVATE_DETAIL")):
            with self.assertRaisesRegex(client.ClientError, "Connection failed") as caught:
                client.request(health=True)
            self.assertNotIn("PRIVATE_DETAIL", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
