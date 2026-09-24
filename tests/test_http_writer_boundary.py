"""Local HTTP regressions; no Hub, provider, or external network writes."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch

from space import server as sink


TOKEN = "test-only-writer-token-not-a-real-secret-0123456789"


class WriterBoundaryTests(unittest.TestCase):
    def setUp(self):
        sink.LEDGER.clear()
        self.env = patch.dict(sink.os.environ, {"EVIDENCE_STUDIO_WRITE_TOKEN": TOKEN})
        self.env.start()
        self.server = sink.ThreadingHTTPServer(("127.0.0.1", 0), sink.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.env.stop()
        sink.LEDGER.clear()

    def request(self, method="POST", path="/api/merge", body=None, headers=None):
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            conn.close()

    def post(self, body=None, **headers):
        return self.request(body=json.dumps(body or {"packet": "counsel"}), headers={
            "Content-Type": "application/json", **headers,
        })

    def test_unauthenticated_write_does_not_append(self):
        status, body, _ = self.post()
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["error"], "WRITER_AUTH_REQUIRED")
        self.assertEqual(sink.LEDGER, [])

    def test_unconfigured_writer_fails_closed(self):
        with patch.dict(sink.os.environ, {"EVIDENCE_STUDIO_WRITE_TOKEN": ""}):
            status, body, _ = self.post(Authorization="Bearer " + TOKEN)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)["error"], "WRITER_NOT_CONFIGURED")
        self.assertEqual(sink.LEDGER, [])

    def test_wrong_token_does_not_append(self):
        for authorization in ("Bearer wrong", "Basic " + TOKEN, "Bearer caf\xe9"):
            status, _, _ = self.post(Authorization=authorization)
            self.assertEqual(status, 401)
        self.assertEqual(sink.LEDGER, [])

    def test_authenticated_known_packet_uses_existing_merge(self):
        status, body, _ = self.post(Authorization="Bearer " + TOKEN)
        record = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(record["decision"], "ALLOW")
        self.assertEqual(record["honesty_tier"], "STRUCTURAL-ONLY")
        self.assertEqual(record["signer"], "UNSIGNED-honest")
        self.assertEqual(len(sink.LEDGER), 1)
        self.assertNotIn(TOKEN, body.decode())

    def test_authenticated_unknown_packet_still_blocked(self):
        status, body, _ = self.post({"packet": "unknown"}, Authorization="Bearer " + TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["decision"], "BLOCKED")
        self.assertEqual(sink.LEDGER, [])

    def test_malformed_json_and_non_object_rejected(self):
        for payload in (
            b"{", b"[]", b"null", b'{"packet":"counsel","packet":"immune"}',
            b'{"packet":"counsel","extra":NaN}',
            b'{"packet":"counsel","extra":Infinity}',
            b'{"packet":"counsel","extra":-Infinity}',
            b'{"packet":123}', b'{"packet":"counsel","evidence":null}',
        ):
            status, body, _ = self.request(body=payload, headers={
                "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
            })
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(body)["error"], "INVALID_JSON_OBJECT")
        self.assertEqual(sink.LEDGER, [])

    def test_oversized_body_rejected(self):
        status, _, _ = self.request(body=b"x" * 16385, headers={
            "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
        })
        self.assertEqual(status, 413)
        self.assertEqual(sink.LEDGER, [])

    def test_unsupported_media_type_rejected(self):
        status, _, _ = self.request(body=b'{"packet":"counsel"}', headers={
            "Authorization": "Bearer " + TOKEN, "Content-Type": "text/plain",
        })
        self.assertEqual(status, 415)
        self.assertEqual(sink.LEDGER, [])

    def test_invalid_content_length_rejected(self):
        for length in ("-1", "nonsense"):
            status, _, _ = self.request(body=b"", headers={
                "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
                "Content-Length": length,
            })
            self.assertEqual(status, 400)
        self.assertEqual(sink.LEDGER, [])

    def test_chunked_body_rejected(self):
        status, _, _ = self.request(body=b"0\r\n\r\n", headers={
            "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
            "Transfer-Encoding": "chunked",
        })
        self.assertEqual(status, 400)

    def test_authorization_checked_before_body_read(self):
        # Advertise an unsent body. A body-first implementation would time out.
        status, _, _ = self.request(body=b"", headers={
            "Content-Length": "10000", "Content-Type": "application/json",
        })
        self.assertEqual(status, 401)
        self.assertEqual(sink.LEDGER, [])

    def test_short_or_whitespace_writer_configuration_disabled(self):
        for token in ("short", " " + TOKEN, TOKEN + "\n"):
            with patch.dict(sink.os.environ, {"EVIDENCE_STUDIO_WRITE_TOKEN": token}):
                status, _, _ = self.post(Authorization="Bearer " + TOKEN)
            self.assertEqual(status, 503)
        self.assertEqual(sink.LEDGER, [])

    def test_ambiguous_headers_and_missing_length_rejected(self):
        cases = (
            ([("Authorization", "Bearer " + TOKEN)] * 2 + [("Content-Length", "0")], 401),
            ([("Authorization", "Bearer " + TOKEN)] + [("Content-Length", "0")] * 2, 400),
            ([("Authorization", "Bearer " + TOKEN)], 411),
        )
        for headers, expected in cases:
            conn = http.client.HTTPConnection(*self.server.server_address, timeout=3)
            try:
                conn.putrequest("POST", "/api/merge")
                conn.putheader("Content-Type", "application/json")
                for name, value in headers:
                    conn.putheader(name, value)
                conn.endheaders()
                response = conn.getresponse()
                self.assertEqual(response.status, expected)
                response.read()
            finally:
                conn.close()
        self.assertEqual(sink.LEDGER, [])

    def test_public_gets_remain_readable_and_never_leak_token(self):
        for path in ("/", "/api/packets", "/api/ledger", "/healthz"):
            status, body, _ = self.request(method="GET", path=path)
            self.assertEqual(status, 200)
            self.assertNotIn(TOKEN, body.decode())

    def test_public_page_does_not_initiate_writes(self):
        status, body, _ = self.request(method="GET", path="/")
        self.assertEqual(status, 200)
        self.assertNotIn(b'fetch("/api/merge"', body)
        self.assertIn(b"read-only", body)


if __name__ == "__main__":
    unittest.main()
