import unittest

from space import server as sink

# Ids retired from the Hub (absent from the SZLHOLDINGS Space list, 2026-09-29).
# Their packets must fail closed as unknown; they are never re-listed as sources.
RETIRED = (
    "holographic",
    "anatomy",
    "cosmos",
    "lyte-services",
    "szl-real-estate",
    "szl-sovereign-os",
    "evidence-studio",
)


class PacketSourceTests(unittest.TestCase):
    def setUp(self):
        sink.LEDGER.clear()

    def test_sources_are_unique_org_space_ids(self):
        ids = [source["id"] for source in sink.SOURCES]
        self.assertEqual(len(ids), len(set(ids)))
        for source in sink.SOURCES:
            self.assertEqual(source["hub"], "SZLHOLDINGS/" + source["id"])
            self.assertIn(source["class"], {"hologram", "receipt"})

    def test_no_retired_space_is_a_source(self):
        listed = {source["id"] for source in sink.SOURCES}
        self.assertEqual(set(), listed & set(RETIRED))

    def test_retired_packets_fail_closed_without_appending(self):
        for packet in RETIRED:
            rec = sink.merge(packet, "evidence", "")
            self.assertEqual(rec["decision"], "BLOCKED", packet)
            self.assertEqual(rec["honesty_tier"], "UNAVAILABLE", packet)
        self.assertEqual(sink.LEDGER, [])

    def test_health_reports_the_computed_source_count(self):
        self.assertEqual(len(sink.KNOWN), len(sink.SOURCES))


if __name__ == "__main__":
    unittest.main()
