from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Metric(BaseModel):
    """One measured value with its source and measurement window."""

    name: str = Field(min_length=1)
    value: float | int
    unit: str = Field(min_length=1)
    source: Literal["github", "huggingface", "cloudflare", "derived"]
    observed_at: datetime
    window_start: datetime | None = None
    window_end: datetime | None = None
    evidence_url: HttpUrl | None = None
    status: Literal["observed", "unavailable", "estimated"] = "observed"
    note: str | None = None

    @field_validator("observed_at", "window_start", "window_end")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value


class MonetizationFunnel(BaseModel):
    """Explicit payment funnel counts; no implicit conversion of missing values."""

    payment_required: int = Field(ge=0)
    authorized: int | None = Field(default=None, ge=0)
    settled: int | None = Field(default=None, ge=0)
    recognized_revenue_usd: float | None = Field(default=None, ge=0)
    source: Literal["cloudflare", "derived"] = "cloudflare"
    observed_at: datetime
    evidence_url: HttpUrl | None = None

    @property
    def settlement_rate(self) -> float | None:
        if self.settled is None or self.payment_required == 0:
            return None
        return self.settled / self.payment_required


class X402State(BaseModel):
    """Operational state for the payment wire, kept separate from revenue."""

    protocol: Literal["x402"] = "x402"
    version: str = "unknown"
    state: Literal["disabled", "challenge_only", "authorization_seen", "settlement_verified", "blocked"]
    challenges: int = Field(default=0, ge=0)
    authorizations: int | None = Field(default=None, ge=0)
    settlements: int | None = Field(default=None, ge=0)
    failure_reason: str | None = None
    observed_at: datetime
    evidence_url: HttpUrl | None = None


class Snapshot(BaseModel):
    """Cross-platform snapshot consumed by the API, frontend, and HF exports."""

    schema_version: Literal["szl.observatory.snapshot/v1"] = "szl.observatory.snapshot/v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metrics: list[Metric] = Field(default_factory=list)
    monetization: MonetizationFunnel | None = None
    x402: X402State | None = None
    provenance: list[str] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def generated_at_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must include a timezone")
        return value


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    snapshot_generated_at: datetime
