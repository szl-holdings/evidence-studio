from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .models import HealthResponse, Snapshot
from .service import load_snapshot


def create_app(snapshot: Snapshot | None = None) -> FastAPI:
    app = FastAPI(
        title="SZL Observatory",
        version=__version__,
        description="Evidence-first analytics and monetization telemetry for SZL Holdings.",
    )
    if snapshot is not None:
        current = snapshot
    elif os.getenv("SZL_SNAPSHOT_FILE"):
        current = load_snapshot(Path(os.environ["SZL_SNAPSHOT_FILE"]))
    else:
        current = load_snapshot()

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(version=__version__, snapshot_generated_at=current.generated_at)

    @app.get("/api/v1/snapshot", response_model=Snapshot)
    def get_snapshot() -> Snapshot:
        return current

    @app.get("/api/v1/metrics")
    def get_metrics(source: str | None = None) -> list[dict]:
        if source is None:
            return [metric.model_dump(mode="json") for metric in current.metrics]
        if source not in {"github", "huggingface", "cloudflare", "derived"}:
            raise HTTPException(status_code=400, detail="unsupported source")
        return [metric.model_dump(mode="json") for metric in current.metrics if metric.source == source]

    @app.get("/api/v1/monetization")
    def get_monetization() -> dict:
        if current.monetization is None:
            raise HTTPException(status_code=404, detail="monetization data unavailable")
        return current.monetization.model_dump(mode="json")

    @app.get("/api/v1/reconciliation")
    def get_reconciliation() -> dict:
        from .reconcile import reconcile
        return reconcile(current)

    @app.get("/api/v1/x402")
    def get_x402() -> dict:
        if current.x402 is None:
            raise HTTPException(status_code=404, detail="x402 state unavailable")
        return current.x402.model_dump(mode="json")

    packaged_frontend = Path(__file__).resolve().parent / "frontend" / "index.html"
    source_frontend = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    frontend = packaged_frontend if packaged_frontend.exists() else source_frontend
    frontend_dir = frontend.parent
    if frontend_dir.exists():
        app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        if not frontend.exists():
            raise HTTPException(status_code=404, detail="frontend not built")
        return FileResponse(frontend)

    return app


app = create_app()
