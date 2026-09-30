#!/usr/bin/env python3
"""Derive the sink's Hub Space observation from the generated public inventory.

szl-holdings/a11oy-net generates the public Hub inventory from the live
Hugging Face API and serves it at INVENTORY_URL. This script reads that file,
verifies its schema, organization, space count and content hash, and writes
space/hub_spaces.json: the sorted public Space ids plus the observation they
came from. The sink (space/server.py) reads only that file, so a packet source
is accepted only while the generated inventory lists its Space.

Nothing here writes to the Hub.

Usage:
  python scripts/refresh_hub_spaces.py                  fetch INVENTORY_URL, write
  python scripts/refresh_hub_spaces.py --inventory F    derive from a saved copy
  python scripts/refresh_hub_spaces.py --check          exit 1 if the file is stale
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

INVENTORY_URL = "https://a11oy.net/public-inventory.json"
SUPPORTED_INVENTORY_SCHEMAS = frozenset({"szl.public-hf-inventory/v4"})
ORGANIZATION = "SZLHOLDINGS"
OUTPUT_SCHEMA = "evidence-studio.hub-spaces/v1"
GENERATED_BY = "scripts/refresh_hub_spaces.py"
OUTPUT = Path(__file__).resolve().parent.parent / "space" / "hub_spaces.json"
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class InventoryError(ValueError):
    """The inventory cannot be trusted as an observation. Nothing is written."""


def canonical(value: Any) -> bytes:
    # Same canonical form a11oy-net uses to compute content_sha256.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def content_sha256(inventory: dict[str, Any]) -> str:
    body = {k: v for k, v in inventory.items() if k not in ("observed_at", "content_sha256")}
    return hashlib.sha256(canonical(body)).hexdigest()


def derive(inventory: Any, url: str = INVENTORY_URL) -> dict[str, Any]:
    """Return the hub_spaces.json document for one inventory, or raise InventoryError."""
    if not isinstance(inventory, dict):
        raise InventoryError("inventory is not a JSON object")
    schema = inventory.get("schema")
    if schema not in SUPPORTED_INVENTORY_SCHEMAS:
        raise InventoryError(f"unsupported inventory schema: {schema!r}")
    if inventory.get("organization") != ORGANIZATION:
        raise InventoryError(f"inventory organization is not {ORGANIZATION}")
    observed_at = inventory.get("observed_at")
    if not isinstance(observed_at, str) or ISO_UTC.fullmatch(observed_at) is None:
        raise InventoryError("inventory observed_at is not an ISO-8601 UTC timestamp")
    reported = inventory.get("content_sha256")
    if reported != content_sha256(inventory):
        raise InventoryError("inventory content_sha256 does not match its content")

    resources = inventory.get("resources")
    rows = resources.get("spaces") if isinstance(resources, dict) else None
    if not isinstance(rows, list):
        raise InventoryError("inventory has no resources.spaces list")
    ids = []
    for row in rows:
        ident = row.get("id") if isinstance(row, dict) else None
        if not isinstance(ident, str) or not ident.startswith(ORGANIZATION + "/") or ident == ORGANIZATION + "/":
            raise InventoryError(f"space row without an {ORGANIZATION}/<name> id: {ident!r}")
        ids.append(ident)
    if len(ids) != len(set(ids)):
        raise InventoryError("inventory lists a space id twice")
    counts = inventory.get("counts")
    if not isinstance(counts, dict) or counts.get("spaces") != len(ids):
        raise InventoryError("inventory counts.spaces does not match resources.spaces")

    boundaries = inventory.get("claim_boundaries")
    private_assets = boundaries.get("private_assets") if isinstance(boundaries, dict) else None
    return {
        "schema": OUTPUT_SCHEMA,
        "generated_by": GENERATED_BY,
        "observation": {
            "url": url,
            "inventory_schema": schema,
            "observed_at": observed_at,
            "observation_mode": inventory.get("observation_mode"),
            "content_sha256": reported,
            "private_assets": private_assets,
        },
        "spaces": sorted(ids),
    }


def render(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, ensure_ascii=True) + "\n"


def fetch(url: str = INVENTORY_URL) -> Any:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "szl-evidence-studio-refresh"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URL
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--inventory", type=Path, help="derive from a saved inventory file instead of fetching")
    parser.add_argument("--check", action="store_true", help="compare with the committed file; write nothing")
    args = parser.parse_args(argv)

    try:
        if args.inventory:
            inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        else:
            inventory = fetch()
        text = render(derive(inventory))
    except (OSError, ValueError) as error:
        print(f"refresh_hub_spaces: FAIL CLOSED: {error}", file=sys.stderr)
        return 2

    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != text:
            print(f"refresh_hub_spaces: STALE: {OUTPUT.name} differs from the inventory; rerun without --check")
            return 1
        print(f"refresh_hub_spaces: CURRENT: {OUTPUT.name} matches the inventory")
        return 0

    OUTPUT.write_text(text, encoding="utf-8", newline="\n")
    document = json.loads(text)
    print(
        f"refresh_hub_spaces: wrote {OUTPUT.name}: {len(document['spaces'])} spaces"
        f" observed_at {document['observation']['observed_at']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
