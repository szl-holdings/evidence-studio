# SZL Observatory release gates

This package is the canonical implementation. The GitHub repository is the source of
truth; PyPI, the Hugging Face dataset/model/Space/kernel, and Cloudflare routes are
derived surfaces tied to one Git tag and one snapshot receipt.

## First release

1. Run unit, API, receipt, and offline replay tests.
2. Build and inspect the wheel and sdist in a clean environment.
3. Publish an immutable Hugging Face snapshot with source windows, query filters,
   evidence URLs, status, and hashes.
4. Run the Space frontend against that snapshot and verify cold start and error states.
5. Publish the kernel with pinned package/tag and input/output hashes.
6. Deploy the read-only Cloudflare route and map route revision to the Git tag.
7. Keep monetization gated until the x402 fixture passes authorization, replay,
   duplicate handling, settlement confirmation, and receipt append.

## Claims policy

`payment_required` is a challenge, not revenue. Revenue is recognized only from a
verified `settled` event. `estimated` seed values are not live analytics. Missing or
conflicting provider data remains explicit and is never replaced with a guess.
