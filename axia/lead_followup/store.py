"""SQLite storage for leads and the messages sent to them."""

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'web',
    created_at TEXT NOT NULL,
    replied INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sent (
    lead_id INTEGER NOT NULL REFERENCES leads(id),
    step INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (lead_id, step)
);
"""


@dataclass
class Lead:
    id: int
    name: str
    email: str
    phone: str
    message: str
    source: str
    created_at: datetime
    replied: bool


def now():
    return datetime.now(timezone.utc)


class Store:
    def __init__(self, path):
        # The webhook serves requests on worker threads; it serializes access with a lock.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def add_lead(self, name, email, phone="", message="", source="web", created_at=None):
        """Save a lead and return it. A repeat email returns the existing lead."""
        name, email = name.strip(), email.strip().lower()
        if not name:
            raise ValueError("name is required")
        if not EMAIL_RE.match(email):
            raise ValueError(f"invalid email: {email!r}")
        created = (created_at or now()).isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO leads (name, email, phone, message, source, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (name, email, phone.strip(), message.strip(), source, created),
            )
        return self.get_by_email(email)

    def get_by_email(self, email):
        row = self.conn.execute(
            "SELECT * FROM leads WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        return _to_lead(row) if row else None

    def mark_replied(self, email):
        """Stop follow-ups for a lead who has answered."""
        with self.conn:
            cur = self.conn.execute(
                "UPDATE leads SET replied = 1 WHERE email = ?", (email.strip().lower(),)
            )
        return cur.rowcount > 0

    def open_leads(self):
        rows = self.conn.execute("SELECT * FROM leads WHERE replied = 0 ORDER BY id")
        return [_to_lead(r) for r in rows]

    def all_leads(self):
        return [_to_lead(r) for r in self.conn.execute("SELECT * FROM leads ORDER BY id")]

    def sent_steps(self, lead_id):
        rows = self.conn.execute("SELECT step FROM sent WHERE lead_id = ?", (lead_id,))
        return {r["step"] for r in rows}

    def record_sent(self, lead_id, step, when=None):
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO sent (lead_id, step, sent_at) VALUES (?, ?, ?)",
                (lead_id, step, (when or now()).isoformat()),
            )


def _to_lead(row):
    return Lead(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        message=row["message"],
        source=row["source"],
        created_at=datetime.fromisoformat(row["created_at"]),
        replied=bool(row["replied"]),
    )
