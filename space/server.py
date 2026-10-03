"""Evidence Studio — merge sink. One writer. Fail closed on unknown packets."""
from __future__ import annotations

import hashlib
import hmac
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
MAX_REQUEST_BYTES = 16384

HUB_SPACES = Path(__file__).with_name("hub_spaces.json")
HUB_SPACES_SCHEMA = "evidence-studio.hub-spaces/v1"

# Candidate packet sources and their class. This is policy: which Spaces may
# send packets. Existence is evidence: a candidate is a source only while the
# generated public Hub inventory lists its Space. That observation is
# hub_spaces.json, written by scripts/refresh_hub_spaces.py from
# https://a11oy.net/public-inventory.json. A candidate the observation does
# not list (a retired Space, or a private one the public inventory cannot see)
# is not a source, and its packets fail closed as unknown.
CANDIDATES = (
    ("szl-khipu", "hologram"),
    ("counsel", "hologram"),
    ("ayllu", "hologram"),
    ("immune", "receipt"),
    ("immune-lattice", "receipt"),
    ("a11oy-factory", "receipt"),
)


def load_observation(path: Path = HUB_SPACES) -> dict | None:
    """Return {"observed_at", "spaces"} from hub_spaces.json, or None if unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != HUB_SPACES_SCHEMA:
        return None
    spaces = data.get("spaces")
    observation = data.get("observation")
    if not isinstance(spaces, list) or not all(isinstance(s, str) for s in spaces):
        return None
    if not isinstance(observation, dict) or not isinstance(observation.get("observed_at"), str):
        return None
    return {"observed_at": observation["observed_at"], "spaces": frozenset(spaces)}


def derive_sources(observation: dict | None) -> tuple[dict, ...]:
    """Candidates whose Space the observation lists. No observation, no sources."""
    observed = observation["spaces"] if observation else frozenset()
    return tuple(
        {"id": ident, "hub": "SZLHOLDINGS/" + ident, "class": kind}
        for ident, kind in CANDIDATES
        if "SZLHOLDINGS/" + ident in observed
    )


OBSERVATION = load_observation()
SOURCES = derive_sources(OBSERVATION)
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
        requested = prev
        if not isinstance(requested, str):
            return _blocked(key, head, "Invalid prev_hash. Expected a string.")
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
        return body.copy()


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
                        "sources_observed_at": OBSERVATION["observed_at"] if OBSERVATION else None,
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
        if path != "/api/merge":
            self._send(404, b"not found", "text/plain")
            return

        def reject(status: int, error: str) -> None:
            self._send(status, json.dumps({"error": error}).encode(), "application/json")

        # The public UI is read-only. This credential is for a trusted backend,
        # never browser storage, HTML, logs, or a receipt.
        token = os.environ.get("EVIDENCE_STUDIO_WRITE_TOKEN", "")
        if len(token.encode()) < 32 or any(char.isspace() for char in token):
            reject(503, "WRITER_NOT_CONFIGURED")
            return
        authorizations = self.headers.get_all("Authorization", [])
        if len(authorizations) != 1 or not hmac.compare_digest(
            authorizations[0].encode(), ("Bearer " + token).encode()
        ):
            reject(401, "WRITER_AUTH_REQUIRED")
            return
        if self.headers.get_all("Transfer-Encoding"):
            reject(400, "TRANSFER_ENCODING_UNSUPPORTED")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if not lengths:
            reject(411, "CONTENT_LENGTH_REQUIRED")
            return
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdecimal():
            reject(400, "INVALID_CONTENT_LENGTH")
            return
        # Avoid unbounded integer conversion even for malicious header text.
        if len(lengths[0]) > 8 or int(lengths[0]) > MAX_REQUEST_BYTES:
            reject(413, "REQUEST_TOO_LARGE")
            return
        n = int(lengths[0])
        if self.headers.get_content_type() != "application/json":
            reject(415, "JSON_REQUIRED")
            return
        self.connection.settimeout(5)
        try:
            raw = self.rfile.read(n)
        except (TimeoutError, OSError):
            reject(408, "REQUEST_BODY_TIMEOUT")
            return

        def unique_object(pairs: list) -> dict:
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result

        def reject_constant(value: str) -> None:
            raise ValueError("non-JSON numeric constant")

        try:
            data = json.loads(
                raw.decode(), object_pairs_hook=unique_object, parse_constant=reject_constant
            )
            if len(raw) != n or not isinstance(data, dict):
                raise ValueError("object required")
            if any(not isinstance(data.get(key, ""), str) for key in (
                "packet", "evidence", "prev_hash"
            )):
                raise ValueError("string fields required")
        except (ValueError, RecursionError):
            reject(400, "INVALID_JSON_OBJECT")
            return
        rec = merge(data.get("packet", ""), data.get("evidence", ""), data.get("prev_hash", ""))
        self._send(200, json.dumps(rec).encode(), "application/json")


def main() -> None:
    port = int(os.environ.get("PORT", "7860"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    if OBSERVATION is None:
        print("evidence-studio: %s missing or invalid; 0 sources, every packet fails closed"
              % HUB_SPACES.name, flush=True)
    print("evidence-studio listening 0.0.0.0:%s packets=%s" % (port, len(SOURCES)), flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
