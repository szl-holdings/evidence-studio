from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .service import load_snapshot, snapshot_to_json
from .collectors import collect_github_org, collect_huggingface_org, load_cloudflare_export
from .models import Snapshot


def main() -> None:
    parser = argparse.ArgumentParser(prog="szl-observatory")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    export = sub.add_parser("export", help="write a validated snapshot JSON")
    export.add_argument("path", type=Path)
    collect = sub.add_parser("collect", help="collect GitHub/Hugging Face and an operator Cloudflare export")
    collect.add_argument("path", type=Path)
    collect.add_argument("--cloudflare-export", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("szl_observatory.api:app", host=args.host, port=args.port, reload=False)
    elif args.command == "export":
        args.path.write_text(snapshot_to_json(load_snapshot()), encoding="utf-8")
    else:
        now = load_snapshot().generated_at
        metrics = collect_github_org() + collect_huggingface_org() + load_cloudflare_export(args.cloudflare_export)
        snapshot = Snapshot(generated_at=now, metrics=metrics,
                            provenance=["https://github.com/szl-holdings", "https://huggingface.co/SZLHOLDINGS", "https://dash.cloudflare.com/"])
        args.path.write_text(snapshot_to_json(snapshot), encoding="utf-8")


if __name__ == "__main__":
    main()
