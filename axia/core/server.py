"""Small webhook server shared by the agents.

Routes are plain functions taking the parsed body (dict) and returning a
JSON-able result. A built-in /whatsapp route handles Meta's verification
handshake and turns incoming WhatsApp texts into calls to `on_whatsapp`.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def whatsapp_texts(payload):
    """(sender phone, text) for each text message in a WhatsApp webhook payload."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") == "text":
                    yield msg["from"], msg["text"]["body"]


def make_handler(routes, on_whatsapp=None, verify_token=""):
    lock = threading.Lock()  # agents share one SQLite connection

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path == "/health":
                return self._json(200, {"ok": True})
            if (url.path == "/whatsapp" and verify_token
                    and q.get("hub.verify_token") == verify_token):
                return self._send(200, q.get("hub.challenge", "").encode(), "text/plain")
            self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(min(length, 256_000)).decode("utf-8", "replace")
            if "json" in (self.headers.get("Content-Type") or ""):
                try:
                    data = json.loads(raw or "{}")
                except json.JSONDecodeError:
                    return self._json(400, {"error": "invalid JSON"})
            else:
                data = {k: v[0] for k, v in parse_qs(raw).items()}
            if path == "/whatsapp" and on_whatsapp:
                with lock:
                    for phone, text in whatsapp_texts(data):
                        try:
                            on_whatsapp(phone, text)
                        except Exception as e:  # one bad message must not block the rest
                            print(f"failed to handle WhatsApp from {phone}: {e}")
                # Always 200, otherwise WhatsApp re-sends the same messages.
                return self._json(200, {"ok": True})
            if path not in routes:
                return self._json(404, {"error": "not found"})
            try:
                with lock:
                    result = routes[path](data)
            except (TypeError, ValueError, KeyError) as e:
                return self._json(400, {"error": str(e)})
            self._json(200, result)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload, default=str).encode(), "application/json")

        def _send(self, status, body, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(handler, port, host="0.0.0.0"):
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Listening on http://{host}:{port}")
    server.serve_forever()
