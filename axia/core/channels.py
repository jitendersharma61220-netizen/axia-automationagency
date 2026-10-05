"""Ways an agent talks to people: email and WhatsApp.

With AXIA_DRY_RUN=1 (the default) nothing leaves the machine; messages are
printed and kept in memory, which is also how the tests check them.
"""

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage

GRAPH_URL = "https://graph.facebook.com/v21.0/{phone_id}/messages"


class DryRun:
    def __init__(self, out=print):
        self.sent = []
        self.out = out

    def send(self, channel, to, body, subject=""):
        self.sent.append({"channel": channel, "to": to, "subject": subject, "body": body})
        self.out(f"[dry-run] {channel} to={to} {subject!r}")


class Live:
    def __init__(self, env):
        self.env = env

    def send(self, channel, to, body, subject=""):
        if channel == "email":
            self._email(to, subject, body)
        elif channel == "whatsapp":
            self._whatsapp(to, body)
        else:
            raise ValueError(f"unknown channel {channel!r}")

    def _email(self, to, subject, body):
        e = self.env
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = e["AXIA_FROM_EMAIL"], to, subject
        msg.set_content(body)
        with smtplib.SMTP(e["AXIA_SMTP_HOST"], int(e.get("AXIA_SMTP_PORT", "587")), timeout=30) as s:
            s.starttls()
            if e.get("AXIA_SMTP_USER"):
                s.login(e["AXIA_SMTP_USER"], e["AXIA_SMTP_PASSWORD"])
            s.send_message(msg)

    def _whatsapp(self, to, body):
        # Free-form text only reaches people who messaged in the last 24 hours;
        # first contact needs an approved template (configure in Meta).
        e = self.env
        data = json.dumps({"messaging_product": "whatsapp", "to": to,
                           "type": "text", "text": {"body": body}}).encode()
        req = urllib.request.Request(
            GRAPH_URL.format(phone_id=e["AXIA_WA_PHONE_ID"]), data=data, method="POST",
            headers={"Authorization": f"Bearer {e['AXIA_WA_TOKEN']}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()


def make_channels(env=None):
    env = os.environ if env is None else env
    return DryRun() if env.get("AXIA_DRY_RUN", "1") != "0" else Live(env)
