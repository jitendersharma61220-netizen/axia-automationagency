"""SQLite CRM: prospects, every message in and out, and booked meetings."""

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from axia.core.approvals import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    message TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT 'web',
    stage TEXT NOT NULL DEFAULT 'new',
    score INTEGER,
    research TEXT NOT NULL DEFAULT '',
    qualification TEXT NOT NULL DEFAULT '{}',
    followups_sent INTEGER NOT NULL DEFAULT 0,
    next_action_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS prospects_email ON prospects(email);
CREATE INDEX IF NOT EXISTS prospects_phone ON prospects(phone);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    kind TEXT NOT NULL,          -- in, out, note
    channel TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id),
    starts_at TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
"""

# Where a prospect is in the pipeline.
STAGES = ["new", "qualified", "contacted", "replied", "meeting_booked",
          "nurture", "no_response", "disqualified", "lost", "opted_out"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_phone(phone):
    """Digits only, with India's 91 prefix on 10-digit numbers (WhatsApp format)."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return "91" + digits if len(digits) == 10 else digits


@dataclass
class Prospect:
    id: int
    name: str
    email: str
    phone: str
    company: str
    website: str
    message: str
    source: str
    stage: str
    score: int
    research: str
    qualification: dict
    followups_sent: int
    next_action_at: datetime
    created_at: datetime
    updated_at: datetime

    @property
    def first_name(self):
        return self.name.split()[0] if self.name.strip() else ""


class Store:
    def __init__(self, conn, clock=now):
        self.conn = conn
        self.clock = clock
        conn.executescript(SCHEMA)

    def add(self, name, email="", phone="", company="", website="", message="", source="web"):
        """Save a new prospect. A repeat email or phone returns the existing one."""
        name, email, phone = name.strip(), email.strip().lower(), normalize_phone(phone)
        if not name:
            raise ValueError("name is required")
        if email and not EMAIL_RE.match(email):
            raise ValueError(f"invalid email: {email!r}")
        if not email and not phone:
            raise ValueError("email or phone is required")
        existing = self.find(email or phone)
        if existing:
            if message.strip():
                self.log(existing.id, "in", source, message.strip())
            return existing, False
        ts = self.clock().isoformat()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO prospects (name, email, phone, company, website, message, source,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, email, phone, company.strip(), website.strip(), message.strip(),
                 source, ts, ts))
        return self.get(cur.lastrowid), True

    def get(self, prospect_id):
        row = self.conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        return self._prospect(row) if row else None

    def find(self, contact):
        """By email or phone number."""
        contact = (contact or "").strip().lower()
        if "@" in contact:
            row = self.conn.execute("SELECT * FROM prospects WHERE email = ?", (contact,)).fetchone()
        else:
            phone = normalize_phone(contact)
            row = phone and self.conn.execute(
                "SELECT * FROM prospects WHERE phone = ?", (phone,)).fetchone()
        return self._prospect(row) if row else None

    def in_stage(self, *stages):
        marks = ",".join("?" * len(stages))
        rows = self.conn.execute(
            f"SELECT * FROM prospects WHERE stage IN ({marks}) ORDER BY id", stages)
        return [self._prospect(r) for r in rows]

    def all(self):
        return [self._prospect(r) for r in self.conn.execute("SELECT * FROM prospects ORDER BY id")]

    def update(self, prospect_id, **fields):
        if "qualification" in fields:
            fields["qualification"] = json.dumps(fields["qualification"])
        if isinstance(fields.get("next_action_at"), datetime):
            fields["next_action_at"] = fields["next_action_at"].isoformat()
        if fields.get("stage") and fields["stage"] not in STAGES:
            raise ValueError(f"unknown stage {fields['stage']!r}")
        fields["updated_at"] = self.clock().isoformat()
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.conn:
            self.conn.execute(f"UPDATE prospects SET {sets} WHERE id = ?",
                              (*fields.values(), prospect_id))
        return self.get(prospect_id)

    def log(self, prospect_id, kind, channel, body, at=None):
        with self.conn:
            self.conn.execute(
                "INSERT INTO activity (prospect_id, kind, channel, body, at) VALUES (?, ?, ?, ?, ?)",
                (prospect_id, kind, channel, body, (at or self.clock()).isoformat()))

    def history(self, prospect_id):
        rows = self.conn.execute(
            "SELECT kind, channel, body, at FROM activity WHERE prospect_id = ? ORDER BY id",
            (prospect_id,))
        return [dict(r) for r in rows]

    def last_activity(self, prospect_id, kind):
        row = self.conn.execute(
            "SELECT at FROM activity WHERE prospect_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
            (prospect_id, kind)).fetchone()
        return datetime.fromisoformat(row["at"]) if row else None

    def book(self, prospect_id, starts_at):
        """Book a meeting slot. Returns False if someone else just took it."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO meetings (prospect_id, starts_at, created_at) VALUES (?, ?, ?)",
                    (prospect_id, starts_at.isoformat(), self.clock().isoformat()))
        except sqlite3.IntegrityError:  # slot already taken
            return False
        return True

    def booked_slots(self):
        return {datetime.fromisoformat(r["starts_at"])
                for r in self.conn.execute("SELECT starts_at FROM meetings")}

    def meetings(self):
        rows = self.conn.execute(
            "SELECT m.starts_at, p.name, p.company FROM meetings m"
            " JOIN prospects p ON p.id = m.prospect_id ORDER BY m.starts_at")
        return [dict(r) for r in rows]

    def _prospect(self, row):
        return Prospect(
            id=row["id"], name=row["name"], email=row["email"], phone=row["phone"],
            company=row["company"], website=row["website"], message=row["message"],
            source=row["source"], stage=row["stage"], score=row["score"],
            research=row["research"], qualification=json.loads(row["qualification"]),
            followups_sent=row["followups_sent"],
            next_action_at=(datetime.fromisoformat(row["next_action_at"])
                            if row["next_action_at"] else None),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
