"""Cross-provider reconciliation with explicit unknowns."""

from __future__ import annotations

from .models import Snapshot


def reconcile(snapshot: Snapshot) -> dict:
    by_name: dict[str, list[dict]] = {}
    for metric in snapshot.metrics:
        by_name.setdefault(metric.name, []).append(metric.model_dump(mode="json"))
    conflicts = []
    for name, entries in by_name.items():
        values = {entry["value"] for entry in entries if entry["status"] != "unavailable"}
        if len(values) > 1:
            conflicts.append({"metric": name, "values": sorted(values, key=str), "entries": entries})
    return {
        "schema_version": "szl.observatory.reconciliation/v1",
        "generated_at": snapshot.generated_at.isoformat(),
        "metric_groups": by_name,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "unavailable_count": sum(1 for metric in snapshot.metrics if metric.status == "unavailable"),
        "provenance": snapshot.provenance,
    }
