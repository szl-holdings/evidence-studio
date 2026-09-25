"""Exercise both proposed boundaries using only an ephemeral loopback service.

The bearer value below is a synthetic test fixture, never an actual credential.
The small hash delay widens real thread interleavings without replacing hashing.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import http.client
import json
import threading
import time
import unittest
from unittest.mock import patch

from space import server as sink

TOKEN = "synthetic-integration-only-not-a-secret-0123456789"


class LocalTestServer(sink.ThreadingHTTPServer):
    # Avoid listen-backlog failures in this concurrency fixture, not a product change.
    request_queue_size = 32


class WriterLedgerIntegrationTests(unittest.TestCase):
    def setUp(self):
        sink.LEDGER.clear()
        self.environment = patch.dict(sink.os.environ, {"EVIDENCE_STUDIO_WRITE_TOKEN": TOKEN})
        self.environment.start()
        self.server = LocalTestServer(("127.0.0.1", 0), sink.Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.environment.stop()
        sink.LEDGER.clear()
        self.assertFalse(self.thread.is_alive(), "loopback server did not terminate")

    def post(self, body, authorized=True):
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + TOKEN
        conn = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            conn.request("POST", "/api/merge", json.dumps(body), headers)
            response = conn.getresponse()
            raw = response.read()
            self.assertNotIn(TOKEN.encode(), raw)
            return response.status, json.loads(raw)
        finally:
            conn.close()

    def assert_chain(self, expected_count):
        ledger = list(sink.LEDGER)
        self.assertEqual(len(ledger), expected_count)
        previous = sink.GENESIS
        ids = set()
        for record in ledger:
            self.assertEqual(record["prev_hash"], previous)
            self.assertEqual(record["decision"], "ALLOW")
            self.assertEqual(record["honesty_tier"], "STRUCTURAL-ONLY")
            self.assertEqual(record["signer"], "UNSIGNED-honest")
            self.assertIsNone(record["energy"])
            body = {k: v for k, v in record.items() if k != "hash"}
            digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(record["hash"], digest)
            self.assertNotIn(record["id"], ids)
            ids.add(record["id"])
            previous = digest

    def test_authentication_precedes_merge_even_with_valid_current_ancestry(self):
        with patch.object(sink, "merge", wraps=sink.merge) as observed:
            status, _ = self.post({"packet": "counsel", "prev_hash": sink.GENESIS}, authorized=False)
            self.assertEqual(status, 401)
            observed.assert_not_called()
        self.assert_chain(0)

    def test_no_configuration_cannot_reach_ledger(self):
        with patch.dict(sink.os.environ, {"EVIDENCE_STUDIO_WRITE_TOKEN": ""}):
            status, _ = self.post({"packet": "counsel"})
        self.assertEqual(status, 503)
        self.assert_chain(0)

    def test_current_ancestry_and_authentication_work_together(self):
        status, first = self.post({"packet": "counsel", "evidence": "fixture"})
        self.assertEqual(status, 200)
        status, second = self.post({"packet": "anatomy", "prev_hash": first["hash"]})
        self.assertEqual(status, 200)
        self.assertEqual(second["decision"], "ALLOW")
        self.assert_chain(2)

    def test_authenticated_stale_ancestry_never_appends(self):
        self.post({"packet": "counsel"})
        before = json.dumps(sink.LEDGER, sort_keys=True)
        status, blocked = self.post({"packet": "anatomy", "prev_hash": sink.GENESIS})
        self.assertEqual(status, 200)
        self.assertEqual(blocked["decision"], "BLOCKED")
        self.assertEqual(json.dumps(sink.LEDGER, sort_keys=True), before)
        self.assert_chain(1)

    def test_authenticated_foreign_ancestry_never_appends(self):
        _, blocked = self.post({"packet": "counsel", "prev_hash": "a" * 64})
        self.assertEqual(blocked["decision"], "BLOCKED")
        self.assert_chain(0)

    def test_whitespace_only_ancestry_is_not_an_omitted_precondition(self):
        for value in (" ", "\t", "\r\n", "\u2003"):
            with self.subTest(value=repr(value)):
                sink.LEDGER.clear()
                status, record = self.post({"packet": "counsel", "prev_hash": value})
                self.assertEqual(status, 200)
                self.assertEqual(record["decision"], "BLOCKED")
                self.assert_chain(0)

    def test_padded_current_ancestry_is_rejected_without_normalization(self):
        for value in (" " + sink.GENESIS, sink.GENESIS + "\n", "\t" + sink.GENESIS + " "):
            with self.subTest(value=repr(value)):
                sink.LEDGER.clear()
                _, record = self.post({"packet": "counsel", "prev_hash": value})
                self.assertEqual(record["decision"], "BLOCKED")
                self.assert_chain(0)

    def test_malformed_canonical_hashes_remain_rejected(self):
        for value in ("g" * 64, "A" * 64, "0" * 63, "0" * 65):
            with self.subTest(value=value):
                sink.LEDGER.clear()
                _, record = self.post({"packet": "counsel", "prev_hash": value})
                self.assertEqual(record["decision"], "BLOCKED")
                self.assert_chain(0)

    def test_nonstring_http_preconditions_remain_input_errors(self):
        for value in (None, False, 0, [], {}):
            with self.subTest(value=value):
                status, _ = self.post({"packet": "counsel", "prev_hash": value})
                self.assertEqual(status, 400)
                self.assert_chain(0)

    def test_direct_nonstring_preconditions_fail_closed(self):
        for value in (None, False, 0, [], {}):
            with self.subTest(value=value):
                sink.LEDGER.clear()
                record = sink.merge("counsel", "fixture", value)
                self.assertEqual(record["decision"], "BLOCKED")
                self.assert_chain(0)

    def test_empty_and_absent_preconditions_preserve_existing_semantics(self):
        self.post({"packet": "counsel"})
        _, accepted = self.post({"packet": "anatomy", "prev_hash": ""})
        self.assertEqual(accepted["decision"], "ALLOW")
        self.assert_chain(2)

    def test_unknown_packet_with_authentication_stays_blocked(self):
        status, record = self.post({"packet": "unknown", "prev_hash": sink.GENESIS})
        self.assertEqual(status, 200)
        self.assertEqual(record["decision"], "BLOCKED")
        self.assert_chain(0)

    def test_parallel_authenticated_writes_produce_one_linear_chain(self):
        original_hash = sink._sha256

        def slow_hash(body):
            time.sleep(0.004)
            return original_hash(body)

        with patch.object(sink, "_sha256", side_effect=slow_hash):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda n: self.post({"packet": "counsel", "evidence": str(n)}), range(16)))
        self.assertTrue(all(status == 200 and record["decision"] == "ALLOW" for status, record in results))
        self.assert_chain(16)

    def test_parallel_same_head_preconditions_have_only_one_winner(self):
        _, first = self.post({"packet": "counsel"})
        original_hash = sink._sha256

        def slow_hash(body):
            time.sleep(0.004)
            return original_hash(body)

        with patch.object(sink, "_sha256", side_effect=slow_hash):
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(lambda n: self.post({"packet": "anatomy", "prev_hash": first["hash"], "evidence": str(n)}), range(16)))
        self.assertTrue(all(status == 200 for status, _ in results))
        self.assertEqual(sum(record["decision"] == "ALLOW" for _, record in results), 1)
        self.assertEqual(sum(record["decision"] == "BLOCKED" for _, record in results), 15)
        self.assert_chain(2)


if __name__ == "__main__":
    unittest.main()
