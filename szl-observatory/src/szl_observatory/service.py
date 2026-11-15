from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import Metric, MonetizationFunnel, Snapshot, X402State


def default_snapshot() -> Snapshot:
    """Return the current explicitly-labelled baseline.

    These are seed values for local preview only. Production jobs should replace
    them with authenticated exports from each provider and preserve the evidence URL.
    """

    now = datetime.now(timezone.utc)
    return Snapshot(
        generated_at=now,
        metrics=[
            Metric(
                name="repositories", value=153, unit="count", source="github",
                observed_at=now, status="estimated",
                evidence_url="https://github.com/szl-holdings",
                note="Seed baseline; validate against the live organization census.",
            ),
            Metric(
                name="models", value=79, unit="count", source="huggingface",
                observed_at=now, status="estimated",
                evidence_url="https://huggingface.co/SZLHOLDINGS",
                note="Seed baseline; validate against the live organization inventory.",
            ),
            Metric(
                name="datasets", value=49, unit="count", source="huggingface",
                observed_at=now, status="estimated",
                evidence_url="https://huggingface.co/SZLHOLDINGS",
            ),
            Metric(
                name="spaces", value=46, unit="count", source="huggingface",
                observed_at=now, status="estimated",
                evidence_url="https://huggingface.co/SZLHOLDINGS",
            ),
            Metric(
                name="payment_required_challenges", value=23800, unit="count", source="cloudflare",
                observed_at=now, status="estimated",
                evidence_url="https://a-11-oy.com",
                note="Reported operating baseline; reconcile exact dashboard window.",
            ),
            Metric(
                name="settlements", value=0, unit="count", source="cloudflare",
                observed_at=now, status="observed",
                evidence_url="https://a-11-oy.com",
                note="Reported operating baseline; verify against settlement records.",
            ),
        ],
        monetization=MonetizationFunnel(
            payment_required=23800,
            authorized=None,
            settled=0,
            recognized_revenue_usd=0.0,
            observed_at=now,
            evidence_url="https://a-11-oy.com",
        ),
        x402=X402State(
            version="coinbase-v2",
            state="blocked",
            challenges=23800,
            settlements=0,
            failure_reason="Settlement wire compatibility must be verified against the live Coinbase x402 v2 payload format.",
            observed_at=now,
            evidence_url="https://a-11-oy.com",
        ),
        provenance=[
            "https://github.com/szl-holdings",
            "https://huggingface.co/SZLHOLDINGS",
            "https://a-11-oy.com",
        ],
    )


def load_snapshot(path: Path | None = None) -> Snapshot:
    """Load a validated snapshot export, or use the labelled local baseline."""

    if path is None:
        return default_snapshot()
    return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))


def snapshot_to_json(snapshot: Snapshot) -> str:
    return snapshot.model_dump_json(indent=2)
