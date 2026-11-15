# Monetization contract

The Cloudflare edge may meter requests, but the product exposes these states
separately: `payment_required`, `payment_authorized`, `payment_submitted`, `settled`,
`rejected`, and `unknown`.

The current fixture is intentionally `blocked` with zero settlements. It is not a
revenue claim. Enable payment collection only after the exact x402 wire format,
signature/authorization verification, replay protection, settlement confirmation, and
append-only receipt path pass in CI and in one controlled production canary.
