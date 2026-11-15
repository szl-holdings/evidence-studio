---
language:
- en
license: apache-2.0
pretty_name: SZL Observatory Snapshots
tags:
- analytics
- provenance
- observability
- monetization
---

# SZL Observatory Snapshots

This dataset contains immutable, schema-versioned analytics snapshots for the SZL Holdings estate.

## Evidence policy

Every metric carries a source, timestamp, status, and evidence URL. `observed` means a provider export was captured; `estimated` means a seed or operating-note value awaiting live reconciliation; `unavailable` means the source did not provide the value. Corrections are appended as supersession records and never silently overwrite an earlier snapshot.

## Scope

- GitHub organization activity and repository inventory
- Hugging Face models, datasets, Spaces, and kernels
- Cloudflare Workers, routes, payment-required challenges, authorizations, settlements, and recognized revenue

Do not interpret payment-required challenges as revenue. Revenue is recognized only from verified settlement records.
