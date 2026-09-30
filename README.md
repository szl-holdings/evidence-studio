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

Only Spaces that exist on the Hub are packet sources (`GET /api/packets`).
`space/server.py` holds the candidate list and each candidate's class; that is
policy. Existence is read from the generated public Hub inventory that
`szl-holdings/a11oy-net` publishes at `https://a11oy.net/public-inventory.json`.
`scripts/refresh_hub_spaces.py` fetches it, checks its schema, organization,
space count and `content_sha256`, and writes the public Space ids with that
observation's `observed_at` to `space/hub_spaces.json`. The sink reads only
that file. A candidate it does not list is not a source, and its packets fail
closed as unknown. So does every packet when the file is missing or invalid.
`/healthz` reports the observation as `sources_observed_at`.

The public inventory does not observe private Spaces (`private_assets:
NOT_OBSERVED`). A private candidate, such as `a11oy-factory` in the
2026-09-29T15:33:59Z observation, therefore fails closed until the inventory
lists it. On 2026-09-29 six retired ids were also dropped from the candidate
list: `holographic`, `anatomy`, `cosmos`, `lyte-services`, `szl-real-estate`
and `szl-sovereign-os`. This repository's own standalone Space
(`evidence-studio`) is absent from the Hub; this source makes no claim that it
is running.

To refresh the observation, run `python scripts/refresh_hub_spaces.py` and
commit `space/hub_spaces.json`. `--check` exits 1 when the committed file no
longer matches the live inventory, and writes nothing. CI never fetches it.

POST `/api/merge` accepts a known packet id and returns an UNSIGNED-honest
receipt. Accepted writes are serialized on the server-authoritative ledger
head. A nonempty `prev_hash` must be exact canonical lowercase SHA-256 hex and
must equal that head; whitespace is rejected, never normalized away. A missing
or empty-string precondition retains automatic ancestry selection. Rejected
ancestry does not append to the ledger. Unknown packets fail closed. Energy
UNAVAILABLE. Λ = Conjecture 1.

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
writer configuration or end-to-end readiness. The process-local lock prevents
concurrent accepted writes from forking this in-memory ledger; it does not
coordinate multiple processes or provide durable storage. Authentication and
ancestry are both checked before an accepted append. The HTTP contract and
receipt hash format are unchanged; direct non-string ancestry also fails closed.
