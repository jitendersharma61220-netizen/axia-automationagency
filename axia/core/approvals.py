"""Human approval queue.

Agents never send a message or commit a decision that matters on their own
unless the client switches that on. They put it here, a person approves,
edits or rejects it (from the command line today, a dashboard later), and
only then does it happen.
"""

import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    decided_at TEXT
);
"""


def now():
    return datetime.now(timezone.utc)


def connect(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


class Approvals:
    def __init__(self, conn, agent):
        self.conn = conn
        self.agent = agent
        self.handlers = {}  # kind -> function(payload) run on approval

    def on_approve(self, kind, handler):
        self.handlers[kind] = handler

    def request(self, kind, summary, payload, ref=""):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO approvals (agent, kind, ref, summary, payload, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (self.agent, kind, str(ref), summary, json.dumps(payload), now().isoformat()))
        return cur.lastrowid

    def pending(self):
        rows = self.conn.execute(
            "SELECT * FROM approvals WHERE agent = ? AND status = 'pending' ORDER BY id",
            (self.agent,))
        return [dict(r, payload=json.loads(r["payload"])) for r in rows]

    def get(self, item_id):
        r = self.conn.execute(
            "SELECT * FROM approvals WHERE id = ? AND agent = ?", (item_id, self.agent)).fetchone()
        return dict(r, payload=json.loads(r["payload"])) if r else None

    def approve(self, item_id, edits=None):
        """Run the approved action. `edits` overrides payload fields (e.g. body)."""
        item = self._pending_item(item_id)
        payload = dict(item["payload"], **(edits or {}))
        self.handlers[item["kind"]](payload)
        self._decide(item_id, "approved", payload)
        return payload

    def reject(self, item_id):
        self._pending_item(item_id)
        self._decide(item_id, "rejected")

    def _pending_item(self, item_id):
        item = self.get(item_id)
        if item is None or item["status"] != "pending":
            raise ValueError(f"no pending approval #{item_id}")
        return item

    def _decide(self, item_id, status, payload=None):
        with self.conn:
            if payload is None:
                self.conn.execute("UPDATE approvals SET status = ?, decided_at = ? WHERE id = ?",
                                  (status, now().isoformat(), item_id))
            else:
                self.conn.execute(
                    "UPDATE approvals SET status = ?, decided_at = ?, payload = ? WHERE id = ?",
                    (status, now().isoformat(), json.dumps(payload), item_id))


class Outbox:
    """Outgoing messages: sent at once in auto mode, otherwise queued for approval."""

    def __init__(self, approvals, channels, auto_send=False, on_sent=None):
        self.approvals = approvals
        self.channels = channels
        self.auto_send = auto_send
        self.on_sent = on_sent or (lambda payload: None)
        approvals.on_approve("message", self._deliver)

    def send(self, channel, to, body, subject="", ref="", why="", always_review=False):
        payload = {"channel": channel, "to": to, "subject": subject, "body": body, "ref": str(ref)}
        if self.auto_send and not always_review:
            self._deliver(payload)
            return None
        summary = f"{channel} to {to}" + (f" ({why})" if why else "")
        return self.approvals.request("message", summary, payload, ref)

    def _deliver(self, payload):
        self.channels.send(payload["channel"], payload["to"], payload["body"], payload["subject"])
        self.on_sent(payload)
