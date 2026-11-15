"""Provider adapter contracts.

Collectors are intentionally small and side-effect free: authentication and network
transport stay outside the normalization layer. A collector returns raw evidence and
normalized metrics, so the resulting snapshot remains auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .models import Metric


class ProviderAdapter(Protocol):
    name: str

    def collect(self) -> list[Metric]:
        """Collect a bounded set of metrics from one provider."""


class StaticAdapter:
    """Deterministic adapter useful for local previews and replay tests."""

    def __init__(self, name: str, values: dict[str, int | float], evidence_url: str):
        self.name = name
        self.values = values
        self.evidence_url = evidence_url

    def collect(self) -> list[Metric]:
        now = datetime.now(timezone.utc)
        source = self.name if self.name in {"github", "huggingface", "cloudflare"} else "derived"
        return [
            Metric(
                name=key,
                value=value,
                unit="count",
                source=source,
                observed_at=now,
                status="estimated",
                evidence_url=self.evidence_url,
                note="Static adapter value; replace with a live authenticated collector.",
            )
            for key, value in self.values.items()
        ]
