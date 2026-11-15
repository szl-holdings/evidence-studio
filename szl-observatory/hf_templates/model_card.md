---
license: apache-2.0
tags:
- observability
- analytics
- provenance
---

# SZL Observatory Normalizer

The normalizer validates provider metrics against `szl.observatory.snapshot/v1` and preserves evidence metadata. It is a telemetry and reconciliation component; it is not a claim that all seed values are live or production-ready.

## Limitations

The default local snapshot contains labelled seed values. Use authenticated collectors and publish a new immutable snapshot before presenting live analytics.
