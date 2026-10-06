"""HTTP server for the proposal engine.

    python -m axia_engine.server            # http://localhost:8080

Routes
    GET  /health                   liveness check
    GET  /api/services             services the visitor can pick
    POST /api/proposals            run the engine for one visitor (JSON body)
    GET  /api/proposals/<id>       a stored proposal, for the shareable plan page
    GET  /p/<id>/deck              the pitch deck as printable HTML slides
    GET  /<anything else>          the AXIA website, if AXIA_SITE_DIR exists

Uses only the standard library plus the anthropic package.
"""

import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import core, deck
from .intake import IntakeError
from .services import public_catalogue

log = logging.getLogger("axia_engine")

SITE_DIR = Path(os.environ.get("AXIA_SITE_DIR", Path(__file__).resolve().parents[2] / "website"))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
RATE_LIMIT = int(os.environ.get("AXIA_RATE_LIMIT", "5"))  # proposals per visitor IP per hour
TRUST_PROXY = os.environ.get("TRUST_PROXY") == "1"
MAX_BODY = 20_000

_hits = defaultdict(deque)


def _rate_limited(ip):
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


class Handler(SimpleHTTPRequestHandler):
    server_version = "AXIAEngine/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SITE_DIR), **kwargs)

    # ---------------------------------------------------------- helpers

    def _origin(self):
        proto = self.headers.get("X-Forwarded-Proto", "http") if TRUST_PROXY else "http"
        return f"{proto}://{self.headers.get('Host', 'localhost')}"

    def _cors(self):
        origin = self.headers.get("Origin")
        if "*" in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", "*")
        elif origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send(self, status, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if ctype.startswith("application/json") else body).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _client_ip(self):
        if TRUST_PROXY and self.headers.get("X-Forwarded-For"):
            return self.headers["X-Forwarded-For"].split(",")[0].strip()
        return self.client_address[0]

    # ---------------------------------------------------------- routes

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            return self._send(200, {"ok": True})
        if path == "/api/services":
            return self._send(200, {"services": public_catalogue()})
        m = re.fullmatch(r"/api/proposals/([\w-]+)", path)
        if m:
            p = core.load(m.group(1))
            return self._send(200, core.public_view(p)) if p else self._send(404, {"error": "Plan not found"})
        m = re.fullmatch(r"/p/([\w-]+)/deck", path)
        if m:
            p = core.load(m.group(1))
            return self._send(200, deck.render(p), "text/html; charset=utf-8") if p else self._send(404, {"error": "Plan not found"})
        if SITE_DIR.is_dir():
            return super().do_GET()
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/proposals":
            return self._send(404, {"error": "Not found"})
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._send(413, {"error": "Request too large"})
        try:
            form = json.loads(self.rfile.read(length))
        except ValueError:
            return self._send(400, {"error": "Invalid JSON"})
        if _rate_limited(self._client_ip()):
            return self._send(429, {"error": "Too many plans from this connection. Please try again in an hour or WhatsApp us."})
        site = os.environ.get("PUBLIC_SITE_URL") or self._origin()
        api = os.environ.get("PUBLIC_API_URL") or self._origin()
        try:
            proposal = core.build(form, site, api)
        except IntakeError as e:
            return self._send(400, {"error": str(e)})
        except Exception:
            log.exception("proposal failed")
            return self._send(500, {"error": "Something went wrong. Please WhatsApp us and we will send your plan by hand."})
        return self._send(201, core.public_view(proposal, creator=True))

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    log.info("AXIA engine on http://localhost:%d (site: %s)", port, SITE_DIR if SITE_DIR.is_dir() else "not served")
    server.serve_forever()


if __name__ == "__main__":
    main()
