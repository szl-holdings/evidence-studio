"""Canonical hashing and append-only receipt helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def make_receipt(payload: dict[str, Any], previous_hash: str | None = None) -> dict[str, Any]:
    """Create a hash-linked receipt without pretending it is a signature."""

    body = {
        "schema_version": "szl.observatory.receipt/v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "previous_hash": previous_hash,
        "payload": payload,
    }
    body["body_hash"] = sha256_hex(body)
    return body


def verify_receipt(receipt: dict[str, Any]) -> bool:
    expected = receipt.get("body_hash")
    if not expected:
        return False
    body = {key: value for key, value in receipt.items() if key != "body_hash"}
    return sha256_hex(body) == expected
