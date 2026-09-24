---
title: Evidence Studio
emoji: ⚖️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
suggested_hardware: cpu-basic
short_description: Merge sink. One writer. Receipts, not a flagship.
---

# Evidence Studio

Canonical merge sink for holographic and receipt Spaces. **One writer.**
Packet sources stay listed. This Space does not delete them.

POST `/api/merge` accepts a known packet id and returns an UNSIGNED-honest
receipt. Unknown packets fail closed. Energy UNAVAILABLE. Λ = Conjecture 1.

Not a second flagship. Not live inference. BIND_AS_A11OY_PACKAGE.

Source: [szl-holdings/evidence-studio](https://github.com/szl-holdings/evidence-studio).
Hub writes go through Immune.

## HTTP writer boundary

The public page is a read-only catalog. Selecting a packet does not create a
receipt. `GET /api/packets`, `/api/ledger`, and `/healthz` remain public; do not
submit confidential evidence because the ledger is publicly readable.

`POST /api/merge` is reserved for a trusted backend. Configure
`EVIDENCE_STUDIO_WRITE_TOKEN` in the service's secret store with a high-entropy
value of at least 32 bytes and no whitespace. The backend sends that value in
the `Authorization: Bearer` header over HTTPS. Never put it in frontend code,
browser storage, repository files, receipts, or logs. No credential is provisioned
by this source change. An absent/invalid configuration returns 503; missing or
incorrect authorization returns 401 without reading the request body or appending
to the ledger.

Authorized requests require `Content-Type: application/json`, one valid
`Content-Length`, at most 16 KiB, and a JSON object with string fields `packet`,
`evidence`, and `prev_hash` when supplied. Duplicate JSON keys and chunked
transfer encoding are rejected. Body reads have a five-second socket timeout.
These are input bounds, not a production rate limiter or complete denial-of-service
defense; deploy behind an appropriate reverse proxy.

This boundary authenticates the caller only. It does not verify evidence content,
provide durable storage, or turn an unsigned hash into a signature. The existing
ledger is process-local and is lost on restart. `/healthz` reports liveness, not
writer configuration or end-to-end readiness. Ledger ancestry/concurrency repair
is tracked separately in PR #2; this change does not claim to resolve it.
