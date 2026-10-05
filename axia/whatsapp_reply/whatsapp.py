"""WhatsApp Cloud API: receive messages on a webhook and send replies.

Setup (Meta for Developers > WhatsApp): set the webhook URL to
https://<server>/whatsapp, the verify token to AXIA_WA_VERIFY_TOKEN, and
subscribe to "messages".
"""

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import bot

GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_id}/messages"


class DryRunSender:
    def __init__(self, out=print):
        self.sent = []
        self.out = out

    def send(self, to, text):
        self.sent.append((to, text))
        self.out(f"[dry-run] whatsapp to={to}: {text}")


class CloudApiSender:
    def __init__(self, phone_id, token):
        self.url = GRAPH_URL.format(phone_id=phone_id)
        self.token = token

    def send(self, to, text):
        body = json.dumps({
            "messaging_product": "whatsapp", "to": to,
            "type": "text", "text": {"body": text},
        }).encode()
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()


def make_sender(env):
    if env.get("AXIA_DRY_RUN", "1") != "0":
        return DryRunSender()
    return CloudApiSender(env["AXIA_WA_PHONE_ID"], env["AXIA_WA_TOKEN"])


def incoming_texts(payload):
    """(sender phone, text) for each text message in a webhook payload."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if msg.get("type") == "text":
                    yield msg["from"], msg["text"]["body"]


def handle_message(faq, sender, business, phone, text, ai=None, owner_phone=""):
    reply = bot.answer(faq, text, business, ai)
    sender.send(phone, reply.text)
    if reply.handoff and owner_phone:
        sender.send(owner_phone, f"Customer +{phone} needs a personal reply:\n\"{text}\"")
    return reply


def make_handler(faq, sender, business, verify_token, ai=None, owner_phone=""):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            if (url.path == "/whatsapp" and q.get("hub.mode") == "subscribe"
                    and verify_token and q.get("hub.verify_token") == verify_token):
                return self._reply(200, q.get("hub.challenge", "").encode(), "text/plain")
            self._reply(403, b"forbidden", "text/plain")

        def do_POST(self):
            if urlparse(self.path).path != "/whatsapp":
                return self._reply(404, b"not found", "text/plain")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(min(length, 256_000)) or b"{}")
            except json.JSONDecodeError:
                return self._reply(400, b"invalid JSON", "text/plain")
            # Always answer 200, otherwise WhatsApp re-sends the same messages.
            with lock:
                for phone, text in incoming_texts(payload):
                    try:
                        handle_message(faq, sender, business, phone, text, ai, owner_phone)
                    except Exception as e:  # one bad message must not block the rest
                        print(f"failed to answer {phone}: {e}")
            self._reply(200, b"ok", "text/plain")

        def _reply(self, status, body, ctype):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(handler, host="0.0.0.0", port=8001):
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Listening on http://{host}:{port}/whatsapp")
    server.serve_forever()
