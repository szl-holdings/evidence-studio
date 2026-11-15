"""Reproducible Hugging Face kernel companion for SZL Observatory snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from szl_observatory.receipts import make_receipt
from szl_observatory.service import load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("kernel-result.json"))
    args = parser.parse_args()
    snapshot = load_snapshot(args.snapshot)
    payload = snapshot.model_dump(mode="json")
    receipt = make_receipt(payload)
    result = {
        "schema_version": "szl.observatory.kernel-result/v1",
        "snapshot_generated_at": snapshot.generated_at.isoformat(),
        "metric_count": len(snapshot.metrics),
        "receipt": receipt,
        "input_provenance": snapshot.provenance,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
