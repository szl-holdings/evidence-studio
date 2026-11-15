"""Payment state helpers kept separate from revenue recognition."""

from __future__ import annotations

import base64
import json
from enum import StrEnum
from typing import Any


class PaymentState(StrEnum):
    PAYMENT_REQUIRED = "payment_required"
    PAYMENT_AUTHORIZED = "payment_authorized"
    PAYMENT_SUBMITTED = "payment_submitted"
    SETTLED = "settled"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


def decode_x402_payload(payload: str) -> dict[str, Any]:
    """Decode a base64 JSON envelope; signature and settlement verification are separate."""
    value = json.loads(base64.b64decode(payload, validate=True).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("x402 payload must decode to a JSON object")
    return value


def settlement_rate(payment_required: int, settled: int | None) -> float | None:
    if settled is None or payment_required <= 0:
        return None
    return settled / payment_required
