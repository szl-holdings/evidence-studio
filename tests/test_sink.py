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
        self.assertEqual(len(rec["hash"]), 64)
        self.assertEqual(len(sink.LEDGER), 1)

    def test_unknown_fails_closed(self):
        rec = sink.merge("not-a-packet", "", "")
        self.assertEqual(rec["decision"], "BLOCKED")
        self.assertEqual(rec["honesty_tier"], "UNAVAILABLE")
        self.assertEqual(sink.LEDGER, [])

    def test_empty_fails_closed(self):
        rec = sink.merge("", "", "")
        self.assertEqual(rec["decision"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
