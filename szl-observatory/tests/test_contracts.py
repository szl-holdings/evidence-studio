import unittest
import asyncio
import base64
import json
from datetime import datetime, timezone

import httpx

from szl_observatory.models import Metric, MonetizationFunnel, Snapshot
from szl_observatory.service import default_snapshot, snapshot_to_json
from szl_observatory.receipts import make_receipt, verify_receipt
from szl_observatory.reconcile import reconcile
from szl_observatory.api import create_app
from szl_observatory.monetization import decode_x402_payload


class SnapshotContractTests(unittest.TestCase):
    def test_seed_snapshot_is_valid_and_provenanced(self):
        snapshot = default_snapshot()
        self.assertEqual(snapshot.schema_version, "szl.observatory.snapshot/v1")
        self.assertGreater(len(snapshot.metrics), 0)
        self.assertTrue(all(metric.evidence_url for metric in snapshot.metrics))

    def test_timezone_is_required(self):
        with self.assertRaises(ValueError):
            Metric(name="x", value=1, unit="count", source="github", observed_at=datetime.now())

    def test_settlement_rate_remains_unavailable_without_settlement_denominator(self):
        funnel = MonetizationFunnel(payment_required=10, settled=None, observed_at=datetime.now(timezone.utc))
        self.assertIsNone(funnel.settlement_rate)

    def test_json_round_trip(self):
        snapshot = default_snapshot()
        restored = Snapshot.model_validate_json(snapshot_to_json(snapshot))
        self.assertEqual(restored.schema_version, snapshot.schema_version)
        self.assertEqual(len(restored.metrics), len(snapshot.metrics))

    def test_receipt_is_hash_linked_and_tamper_evident(self):
        receipt = make_receipt({"snapshot": "abc"})
        self.assertTrue(verify_receipt(receipt))
        receipt["payload"]["snapshot"] = "tampered"
        self.assertFalse(verify_receipt(receipt))

    def test_reconciliation_reports_conflicting_metric_values(self):
        snapshot = default_snapshot()
        snapshot.metrics.append(snapshot.metrics[0].model_copy(update={"value": 154, "source": "derived"}))
        result = reconcile(snapshot)
        self.assertGreaterEqual(result["conflict_count"], 1)

    def test_api_exposes_health_snapshot_and_x402_state(self):
        async def request(path: str):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as client:
                return await client.get(path)

        health = asyncio.run(request("/healthz"))
        snapshot = asyncio.run(request("/api/v1/snapshot"))
        x402 = asyncio.run(request("/api/v1/x402"))
        receipt = asyncio.run(request("/api/v1/receipt"))
        self.assertEqual(health.status_code, 200)
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(x402.json()["state"], "blocked")
        self.assertEqual(receipt.status_code, 200)
        self.assertTrue(verify_receipt(receipt.json()))

    def test_x402_payload_fixture_is_decodable_without_claiming_verification(self):
        encoded = base64.b64encode(json.dumps({"version": "2", "scheme": "exact"}).encode()).decode()
        self.assertEqual(decode_x402_payload(encoded)["version"], "2")


if __name__ == "__main__":
    unittest.main()
