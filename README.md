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
receipt. The sink serializes accepted writes onto its server-authoritative
ledger head. A supplied `prev_hash` must be canonical lowercase SHA-256 hex and
must equal the current head; malformed or stale ancestry fails closed and is
not appended. Unknown packets fail closed. Energy UNAVAILABLE. Λ = Conjecture 1.

The ledger is process-local structural evidence, not a durable datastore or a
cryptographic signature. Not a second flagship. Not live inference.
BIND_AS_A11OY_PACKAGE.

Source: [szl-holdings/evidence-studio](https://github.com/szl-holdings/evidence-studio).
Hub writes go through Immune.
