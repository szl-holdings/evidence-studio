"""Evidence Studio — merge sink. One writer. Fail closed on unknown packets."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HTML = Path(__file__).with_name("index.html")
GENESIS = "0" * 64
HEX64 = re.compile(r"^[0-9a-f]{64}$")

SOURCES = (
    {"id": "holographic", "hub": "SZLHOLDINGS/holographic", "class": "hologram"},
    {"id": "anatomy", "hub": "SZLHOLDINGS/anatomy", "class": "hologram"},
    {"id": "szl-khipu", "hub": "SZLHOLDINGS/szl-khipu", "class": "hologram"},
    {"id": "cosmos", "hub": "SZLHOLDINGS/cosmos", "class": "hologram"},
    {"id": "counsel", "hub": "SZLHOLDINGS/counsel", "class": "hologram"},
    {"id": "ayllu", "hub": "SZLHOLDINGS/ayllu", "class": "hologram"},
    {"id": "immune", "hub": "SZLHOLDINGS/immune", "class": "receipt"},
    {"id": "immune-lattice", "hub": "SZLHOLDINGS/immune-lattice", "class": "receipt"},
    {"id": "a11oy-factory", "hub": "SZLHOLDINGS/a11oy-factory", "class": "receipt"},
    {"id": "lyte-services", "hub": "SZLHOLDINGS/lyte-services", "class": "receipt"},
    {"id": "szl-real-estate", "hub": "SZLHOLDINGS/szl-real-estate", "class": "hologram"},
    {"id": "szl-sovereign-os", "hub": "SZLHOLDINGS/szl-sovereign-os", "class": "hologram"},
)
KNOWN = {s["id"]: s for s in SOURCES}
LEDGER: list[dict] = []
_LEDGER_LOCK = threading.Lock()


def _sha256(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _head_hash() -> str:
    return LEDGER[-1]["hash"] if LEDGER else GENESIS


def _blocked(packet: str, prev_hash: str, note: str) -> dict:
    body = {
        "id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "organ": "circulatory",
        "action": "merge",
        "decision": "BLOCKED",
        "packet": packet or "<empty>",
        "honesty_tier": "UNAVAILABLE",
        "lambda_status": "Conjecture 1",
        "energy": None,
        "signer": "UNSIGNED-honest",
        "bind": "BIND_AS_A11OY_PACKAGE",
        "flagship": "a11oy",
        "prev_hash": prev_hash,
        "note": note,
    }
    body["hash"] = _sha256(body)
    return body


def merge(packet: str, evidence: str, prev: str) -> dict:
    key = (packet or "").strip()
    src = KNOWN.get(key)

    with _LEDGER_LOCK:
        head = _head_hash()
        requested = prev.strip() if isinstance(prev, str) else ""
        if requested:
            if HEX64.fullmatch(requested) is None:
                return _blocked(
                    key,
                    head,
                    "Invalid prev_hash. Expected canonical lowercase sha256 hex.",
                )
            if requested != head:
                return _blocked(
                    key,
                    head,
                    "prev_hash does not match the authoritative ledger head. Fail closed.",
                )

        if src is None:
            return _blocked(
                key,
                head,
                "Unknown packet. Fail closed. This sink does not mint sources.",
            )

        body = {
            "id": str(uuid.uuid4()),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "organ": "circulatory",
            "action": "merge",
            "decision": "ALLOW",
            "packet": src["id"],
            "hub": src["hub"],
            "class": src["class"],
            "evidence": (evidence or "")[:480],
            "honesty_tier": "STRUCTURAL-ONLY",
            "lambda_status": "Conjecture 1",
            "energy": None,
            "signer": "UNSIGNED-honest",
            "bind": "BIND_AS_A11OY_PACKAGE",
            "flagship": "a11oy",
            "prev_hash": head,
            "note": "One writer. Source Space stays listed. Hash is tamper-evident, not a signature.",
        }
        body["hash"] = _sha256(body)
        LEDGER.append(body)
        return body


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
            return
        if path in ("/health", "/healthz"):
            self._send(
                200,
                json.dumps(
                    {
                        "ok": True,
                        "service": "evidence-studio",
                        "bind": "BIND_AS_A11OY_PACKAGE",
                        "writer": "one",
                        "packets": len(SOURCES),
                        "ledger": len(LEDGER),
                        "lambda_status": "Conjecture 1",
                        "energy": None,
                    }
                ).encode(),
                "application/json",
            )
            return
        if path == "/api/packets":
            self._send(200, json.dumps(list(SOURCES)).encode(), "application/json")
            return
        if path == "/api/ledger":
            self._send(200, json.dumps(LEDGER[-50:]).encode(), "application/json")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except Exception:
            data = {}
        if path == "/api/merge":
            rec = merge(
                str(data.get("packet") or ""),
                str(data.get("evidence") or ""),
                str(data.get("prev_hash") or ""),
            )
            self._send(200, json.dumps(rec).encode(), "application/json")
            return
        self._send(404, b"not found", "text/plain")


def main() -> None:
    port = int(os.environ.get("PORT", "7860"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("evidence-studio listening 0.0.0.0:%s packets=%s" % (port, len(SOURCES)), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
