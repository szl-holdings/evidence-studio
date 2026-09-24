import threading
import unittest

from space import server as sink


class SinkTests(unittest.TestCase):
    def setUp(self):
        sink.LEDGER.clear()

    def test_known_packet_allows(self):
        rec = sink.merge("counsel", "allodial packet", "")
        self.assertEqual(rec["decision"], "ALLOW")
        self.assertEqual(rec["signer"], "UNSIGNED-honest")
        self.assertIsNone(rec["energy"])
        self.assertEqual(rec["prev_hash"], sink.GENESIS)
        self.assertEqual(len(rec["hash"]), 64)
        self.assertEqual(len(sink.LEDGER), 1)

    def test_unknown_fails_closed(self):
        rec = sink.merge("not-a-packet", "", "")
        self.assertEqual(rec["decision"], "BLOCKED")
        self.assertEqual(rec["honesty_tier"], "UNAVAILABLE")
        self.assertEqual(rec["prev_hash"], sink.GENESIS)
        self.assertEqual(sink.LEDGER, [])

    def test_empty_fails_closed(self):
        rec = sink.merge("", "", "")
        self.assertEqual(rec["decision"], "BLOCKED")

    def test_noncanonical_prev_hash_fails_closed(self):
        rec = sink.merge("counsel", "", "g" * 64)
        self.assertEqual(rec["decision"], "BLOCKED")
        self.assertEqual(rec["prev_hash"], sink.GENESIS)
        self.assertEqual(sink.LEDGER, [])

    def test_stale_prev_hash_cannot_fork_ledger(self):
        first = sink.merge("counsel", "first", "")
        rec = sink.merge("anatomy", "second", sink.GENESIS)
        self.assertEqual(rec["decision"], "BLOCKED")
        self.assertEqual(rec["prev_hash"], first["hash"])
        self.assertEqual(len(sink.LEDGER), 1)

    def test_exact_current_prev_hash_allows(self):
        first = sink.merge("counsel", "first", "")
        second = sink.merge("anatomy", "second", first["hash"])
        self.assertEqual(second["decision"], "ALLOW")
        self.assertEqual(second["prev_hash"], first["hash"])
        self.assertEqual(len(sink.LEDGER), 2)

    def test_concurrent_merges_form_one_linear_chain(self):
        results = []
        results_lock = threading.Lock()

        def worker(index: int) -> None:
            rec = sink.merge("counsel", f"packet-{index}", "")
            with results_lock:
                results.append(rec)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 16)
        self.assertTrue(all(rec["decision"] == "ALLOW" for rec in results))
        self.assertEqual(len(sink.LEDGER), 16)
        expected_prev = sink.GENESIS
        for rec in sink.LEDGER:
            self.assertEqual(rec["prev_hash"], expected_prev)
            expected_prev = rec["hash"]


if __name__ == "__main__":
    unittest.main()
