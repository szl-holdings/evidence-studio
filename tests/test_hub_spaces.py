"""The sink's packet sources come from the generated public Hub inventory.

space/hub_spaces.json is written by scripts/refresh_hub_spaces.py from
https://a11oy.net/public-inventory.json. These tests run offline: they check
the committed observation's shape, the generator's fail-closed validation on
synthetic inventories, and that the sink derives its sources from the
observation instead of a typed list.
"""
from __future__ import annotations

import copy
import http.client
import importlib.util
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from space import server as sink

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("refresh_hub_spaces", ROOT / "scripts" / "refresh_hub_spaces.py")
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


def synthetic_inventory(space_ids):
    """A minimal v4-shaped inventory with a correct content hash. Not a Hub capture."""
    inventory = {
        "schema": "szl.public-hf-inventory/v4",
        "organization": "SZLHOLDINGS",
        "observed_at": "2026-01-01T00:00:00Z",
        "observation_mode": "UNAUTHENTICATED_PUBLIC_API_SNAPSHOT",
        "claim_boundaries": {"private_assets": "NOT_OBSERVED"},
        "counts": {"spaces": len(space_ids)},
        "resources": {"spaces": [{"id": ident, "runtime": {"stage": "RUNNING"}} for ident in space_ids]},
    }
    inventory["content_sha256"] = refresh.content_sha256(inventory)
    return inventory


def rehash(inventory):
    inventory["content_sha256"] = refresh.content_sha256(inventory)
    return inventory


class CommittedObservationTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads((ROOT / "space" / "hub_spaces.json").read_text(encoding="utf-8"))

    def test_shape_and_provenance(self):
        doc = self.document
        self.assertEqual(doc["schema"], refresh.OUTPUT_SCHEMA)
        self.assertEqual(doc["generated_by"], refresh.GENERATED_BY)
        observation = doc["observation"]
        self.assertEqual(observation["url"], refresh.INVENTORY_URL)
        self.assertIn(observation["inventory_schema"], refresh.SUPPORTED_INVENTORY_SCHEMAS)
        self.assertRegex(observation["observed_at"], refresh.ISO_UTC)
        self.assertRegex(observation["content_sha256"], re.compile(r"^[0-9a-f]{64}$"))

    def test_spaces_are_sorted_unique_org_ids(self):
        spaces = self.document["spaces"]
        self.assertTrue(spaces)
        self.assertEqual(spaces, sorted(set(spaces)))
        for ident in spaces:
            self.assertTrue(ident.startswith("SZLHOLDINGS/"), ident)

    def test_file_is_the_generator_rendering(self):
        text = (ROOT / "space" / "hub_spaces.json").read_text(encoding="utf-8")
        self.assertEqual(text, refresh.render(self.document))

    def test_sink_loaded_the_committed_observation(self):
        self.assertIsNotNone(sink.OBSERVATION)
        self.assertEqual(sink.OBSERVATION["observed_at"], self.document["observation"]["observed_at"])
        self.assertEqual(sink.OBSERVATION["spaces"], frozenset(self.document["spaces"]))

    def test_every_source_is_observed_and_every_observed_candidate_is_a_source(self):
        observed = set(self.document["spaces"])
        for source in sink.SOURCES:
            self.assertIn(source["hub"], observed)
        expected = [ident for ident, _ in sink.CANDIDATES if "SZLHOLDINGS/" + ident in observed]
        self.assertEqual([source["id"] for source in sink.SOURCES], expected)

    def test_public_endpoints_report_the_derived_sources(self):
        server = sink.ThreadingHTTPServer(("127.0.0.1", 0), sink.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            def get(path):
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                try:
                    conn.request("GET", path)
                    response = conn.getresponse()
                    return response.status, json.loads(response.read())
                finally:
                    conn.close()

            status, health = get("/healthz")
            self.assertEqual(status, 200)
            self.assertEqual(health["sources_observed_at"], self.document["observation"]["observed_at"])
            self.assertEqual(health["packets"], len(sink.SOURCES))
            status, packets = get("/api/packets")
            self.assertEqual(status, 200)
            self.assertEqual(packets, list(sink.SOURCES))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_image_ships_the_observation_next_to_the_server(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("COPY space/hub_spaces.json ./hub_spaces.json", dockerfile.splitlines())
        self.assertEqual(sink.HUB_SPACES.name, "hub_spaces.json")
        self.assertEqual(sink.HUB_SPACES.parent, Path(sink.__file__).parent)


class SinkDerivationTests(unittest.TestCase):
    def setUp(self):
        sink.LEDGER.clear()

    def test_unobserved_candidate_is_not_a_source(self):
        observed = {"SZLHOLDINGS/" + ident for ident, _ in sink.CANDIDATES[1:]}
        sources = sink.derive_sources({"observed_at": "2026-01-01T00:00:00Z", "spaces": frozenset(observed)})
        ids = [source["id"] for source in sources]
        self.assertNotIn(sink.CANDIDATES[0][0], ids)
        self.assertEqual(len(ids), len(sink.CANDIDATES) - 1)

    def test_observed_non_candidate_is_not_a_source(self):
        sources = sink.derive_sources({"observed_at": "2026-01-01T00:00:00Z", "spaces": frozenset({"SZLHOLDINGS/README"})})
        self.assertEqual(sources, ())

    def test_no_observation_means_no_sources(self):
        self.assertEqual(sink.derive_sources(None), ())

    def test_unusable_observation_files_load_as_none(self):
        valid = {"schema": sink.HUB_SPACES_SCHEMA, "observation": {"observed_at": "x"}, "spaces": ["SZLHOLDINGS/counsel"]}
        broken = {
            "not json": "{",
            "wrong schema": json.dumps(dict(valid, schema="other/v1")),
            "spaces not a list": json.dumps(dict(valid, spaces="SZLHOLDINGS/counsel")),
            "non-string space": json.dumps(dict(valid, spaces=[1])),
            "no observed_at": json.dumps(dict(valid, observation={})),
            "array": json.dumps([valid]),
        }
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            self.assertIsNone(sink.load_observation(missing))
            for label, text in broken.items():
                path = Path(directory) / "hub_spaces.json"
                path.write_text(text, encoding="utf-8")
                self.assertIsNone(sink.load_observation(path), label)
            path.write_text(json.dumps(valid), encoding="utf-8")
            self.assertEqual(sink.load_observation(path)["spaces"], frozenset({"SZLHOLDINGS/counsel"}))

    def test_packets_fail_closed_when_no_source_is_observed(self):
        with patch.object(sink, "KNOWN", {}):
            record = sink.merge("counsel", "evidence", "")
        self.assertEqual(record["decision"], "BLOCKED")
        self.assertEqual(record["honesty_tier"], "UNAVAILABLE")
        self.assertEqual(sink.LEDGER, [])


class GeneratorTests(unittest.TestCase):
    IDS = ["SZLHOLDINGS/counsel", "SZLHOLDINGS/README", "SZLHOLDINGS/ayllu"]

    def test_derives_sorted_ids_and_provenance(self):
        inventory = synthetic_inventory(self.IDS)
        document = refresh.derive(inventory)
        self.assertEqual(document["schema"], refresh.OUTPUT_SCHEMA)
        self.assertEqual(document["spaces"], sorted(self.IDS))
        self.assertEqual(document["observation"]["observed_at"], inventory["observed_at"])
        self.assertEqual(document["observation"]["content_sha256"], inventory["content_sha256"])
        self.assertEqual(document["observation"]["private_assets"], "NOT_OBSERVED")
        self.assertEqual(refresh.render(document), refresh.render(refresh.derive(copy.deepcopy(inventory))))
        self.assertTrue(refresh.render(document).endswith("}\n"))

    def test_rejects_untrustworthy_inventories(self):
        base = synthetic_inventory(self.IDS)
        cases = {
            "not an object": [],
            "unknown schema": rehash(dict(copy.deepcopy(base), schema="szl.public-hf-inventory/v5")),
            "other organization": rehash(dict(copy.deepcopy(base), organization="someone-else")),
            "bad observed_at": dict(copy.deepcopy(base), observed_at="yesterday"),
            "tampered content": dict(copy.deepcopy(base), counts={"spaces": 99}),
            "duplicate id": synthetic_inventory(self.IDS + ["SZLHOLDINGS/ayllu"]),
            "foreign id": synthetic_inventory(["other/space"]),
            "bare org id": synthetic_inventory(["SZLHOLDINGS/"]),
            "no spaces list": rehash(dict(copy.deepcopy(base), resources={})),
        }
        miscounted = copy.deepcopy(base)
        miscounted["counts"] = {"spaces": len(self.IDS) + 1}
        cases["count mismatch"] = rehash(miscounted)
        for label, inventory in cases.items():
            with self.assertRaises(refresh.InventoryError, msg=label):
                refresh.derive(inventory)

    def test_main_fails_closed_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "inventory.json"
            bad.write_text(json.dumps({"schema": "nope"}), encoding="utf-8")
            target = Path(directory) / "hub_spaces.json"
            with patch.object(refresh, "OUTPUT", target), patch("sys.stderr"):
                self.assertEqual(refresh.main(["--inventory", str(bad)]), 2)
            self.assertFalse(target.exists())

    def test_main_writes_then_check_reports_current_and_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inventory.json"
            source.write_text(json.dumps(synthetic_inventory(self.IDS)), encoding="utf-8")
            target = Path(directory) / "hub_spaces.json"
            with patch.object(refresh, "OUTPUT", target), patch("sys.stdout"):
                self.assertEqual(refresh.main(["--inventory", str(source)]), 0)
                self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["spaces"], sorted(self.IDS))
                self.assertEqual(refresh.main(["--inventory", str(source), "--check"]), 0)
                source.write_text(json.dumps(synthetic_inventory(self.IDS[:1])), encoding="utf-8")
                before = target.read_text(encoding="utf-8")
                self.assertEqual(refresh.main(["--inventory", str(source), "--check"]), 1)
                self.assertEqual(target.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
