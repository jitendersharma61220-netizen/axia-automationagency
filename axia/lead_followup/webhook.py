"""Tiny HTTP endpoint that website forms or Zapier/Make can POST leads to.

POST /lead with JSON or form data: name, email, phone, message, source.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from . import engine

FIELDS = ("name", "email", "phone", "message", "source")


def make_handler(store, mailer, settings):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self._reply(200, {"ok": True})
            else:
                self._reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/lead":
                return self._reply(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(length, 64_000)).decode("utf-8", "replace")
            if "json" in (self.headers.get("Content-Type") or ""):
                try:
                    data = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    return self._reply(400, {"error": "invalid JSON"})
            else:
                data = {k: v[0] for k, v in parse_qs(raw).items()}
            fields = {k: str(data[k]) for k in FIELDS if data.get(k)}
            try:
                with lock:
                    lead = engine.handle_new_lead(store, mailer, settings, **fields)
            except (TypeError, ValueError) as e:
                return self._reply(400, {"error": str(e) or "name and email are required"})
            self._reply(201, {"id": lead.id})

        def _reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(store, mailer, settings, host="0.0.0.0", port=8000):
    server = ThreadingHTTPServer((host, port), make_handler(store, mailer, settings))
    print(f"Listening on http://{host}:{port}  (POST /lead)")
    server.serve_forever()
