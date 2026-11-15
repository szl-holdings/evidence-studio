# SZL Observatory

SZL Observatory is the evidence-first source of truth for the GitHub, Hugging Face, and Cloudflare analytics estate. It provides a validated snapshot contract, a FastAPI read API, a small operator frontend, and an immutable export shape suitable for a Hugging Face dataset.

The repository is deliberately provider-neutral. Production collection jobs should fetch authenticated exports from GitHub, Hugging Face, and Cloudflare, preserve the exact source URL and measurement window, and write a new snapshot. The local baseline is labelled `estimated` where it comes from an operating note rather than a live provider export.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python -m unittest discover -s tests -v
szl-observatory serve --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. API endpoints:

- `GET /healthz`
- `GET /api/v1/snapshot`
- `GET /api/v1/metrics?source=github`
- `GET /api/v1/monetization`
- `GET /api/v1/reconciliation`
- `GET /api/v1/x402`

Set `SZL_SNAPSHOT_FILE=/path/to/snapshot.json` to serve a validated export instead of the seed baseline.

For a live collection run, provide `GITHUB_TOKEN` and `HF_TOKEN` through the
runtime secret store and pass an operator-exported Cloudflare JSON file. The
collector writes a new snapshot; it does not mutate an earlier one:

```bash
szl-observatory collect artifacts/live-2026-11-15.json --cloudflare-export /secure/cloudflare-export.json
```

## Productization path

1. Keep this repository as the governed Python source of truth in `szl-holdings`.
2. Add authenticated provider collectors as separate modules; collectors return raw evidence plus normalized `Metric` objects.
3. Publish immutable snapshots to `SZLHOLDINGS/szl-observatory-snapshots` and link each snapshot to source revisions.
4. Deploy the API behind a governed Cloudflare Worker route. Meter requests at the edge, but recognize revenue only from verified settlement events.
5. Publish the Python package to the `szl-holdings` PyPI organization after CI, provenance, and release checks pass.

The first release also includes receipt hashing (`szl_observatory.receipts`), conflict reporting (`szl_observatory.reconcile`), adapter contracts (`szl_observatory.adapters`), Docker packaging, and Hugging Face dataset/model card templates.

Do not present seed values as live production analytics. The contract requires source, timestamp, status, and evidence URL for every metric.
