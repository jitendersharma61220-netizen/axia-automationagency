"""The clinic assistant: visit notes, lab report explainers, patient reminders.

The doctor stays in charge. Claude drafts; code runs safety checks; nothing
reaches a patient until the doctor approves it.

1. Visit scribe: from the consultation transcript, Claude drafts a SOAP note,
   the prescription and patient instructions in the patient's language. Code
   checks the prescription against recorded allergies, duplicates and missing
   dose/frequency/duration. The doctor approves or edits; then the
   prescription goes to the patient on WhatsApp and reminders are scheduled.
2. Lab reports: Claude reads the report; code re-checks every value against
   its reference range and flags critical values to the doctor at once;
   Claude writes a plain-language explanation that the doctor approves.
3. Reminders: medicine doses and the follow-up visit, sent on time.
"""

import json
import re
from datetime import datetime, timedelta, timezone

from axia.core.approvals import now

IST = timezone(timedelta(hours=5, minutes=30))

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    age INTEGER,
    sex TEXT NOT NULL DEFAULT '',
    allergies TEXT NOT NULL DEFAULT '',
    conditions TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'English'
);
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    transcript TEXT NOT NULL,
    note TEXT NOT NULL,
    warnings TEXT NOT NULL,
    status TEXT NOT NULL,            -- draft, approved, rejected
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    results TEXT NOT NULL,
    explanation TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    send_at TEXT NOT NULL,
    text TEXT NOT NULL,
    sent INTEGER NOT NULL DEFAULT 0
);
"""

_S = {"type": "string"}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


MEDICINE = _obj(
    name=_S, strength=_S,
    dose={"type": "string", "description": "e.g. 1 tablet"},
    frequency={"type": "string", "enum": ["OD", "BD", "TDS", "QID", "HS", "SOS"]},
    duration_days={"type": "integer"},
    instructions={"type": "string", "description": "e.g. after food"},
)

NOTE_SCHEMA = _obj(
    subjective=_S, objective=_S, assessment=_S, plan=_S,
    medicines={"type": "array", "items": MEDICINE},
    tests_advised={"type": "array", "items": _S},
    follow_up_days={"type": "integer", "description": "0 if no follow-up was mentioned"},
    patient_instructions={"type": "string",
                          "description": "for the patient, in their language, simple words"},
)

LAB_SCHEMA = _obj(results={"type": "array", "items": _obj(
    test=_S, value={"type": "number"}, unit=_S,
    low={"type": "number", "description": "reference range low; -1 if not printed"},
    high={"type": "number", "description": "reference range high; -1 if not printed"},
)})

EXPLAIN_SCHEMA = _obj(explanation=_S)

# Values that need the doctor today, whatever the report's own flags say.
CRITICAL = {
    "hemoglobin": (7.0, 20.0), "haemoglobin": (7.0, 20.0),
    "glucose": (50, 400), "potassium": (2.8, 6.0), "sodium": (120, 160),
    "platelet": (20000, 1000000), "creatinine": (0, 4.0),
}

# A patient allergic to the key is also at risk from these medicines.
ALLERGY_GROUPS = {
    "penicillin": ["amoxicillin", "ampicillin", "penicillin", "cloxacillin", "piperacillin"],
    "sulfa": ["sulfamethoxazole", "cotrimoxazole", "sulfasalazine"],
    "nsaid": ["ibuprofen", "diclofenac", "naproxen", "aspirin", "aceclofenac", "ketorolac"],
    "aspirin": ["aspirin"],
    "cephalosporin": ["cefixime", "cefuroxime", "ceftriaxone", "cephalexin", "cefpodoxime"],
}

DOSE_TIMES = {"OD": [9], "BD": [9, 21], "TDS": [8, 14, 20], "QID": [8, 12, 16, 20], "HS": [22]}


def prescription_warnings(medicines, allergies):
    warnings = []
    allergy_words = [a.strip().lower() for a in re.split(r"[,;/]", allergies or "") if a.strip()]
    for m in medicines:
        name = m["name"].lower()
        for allergy in allergy_words:
            risky = [allergy] + [drug for group, drugs in ALLERGY_GROUPS.items()
                                 if group in allergy for drug in drugs]
            if any(r in name for r in risky):
                warnings.append(f"ALLERGY: patient is allergic to {allergy}; "
                                f"{m['name']} is in that group")
        missing = [k for k in ("dose", "frequency") if not m[k]]
        if m["frequency"] != "SOS" and not m["duration_days"]:
            missing.append("duration")
        if missing:
            warnings.append(f"{m['name']}: missing {', '.join(missing)}")
    names = [m["name"].lower().split()[0] for m in medicines if m["name"].strip()]
    for n in sorted({n for n in names if names.count(n) > 1}):
        warnings.append(f"{n} is prescribed more than once")
    return warnings


def flag(result):
    """Recompute low/high/critical from the numbers; never trust a printed flag."""
    v, low, high = result["value"], result["low"], result["high"]
    status = "normal"
    if low >= 0 and v < low:
        status = "low"
    elif high >= 0 and v > high:
        status = "high"
    for key, (crit_low, crit_high) in CRITICAL.items():
        if key in result["test"].lower() and (v < crit_low or v > crit_high):
            status = "critical"
    return status


class ClinicAssistant:
    def __init__(self, conn, ai, approvals, channels, clinic, alert_doctor, clock=now):
        self.conn = conn
        self.ai = ai
        self.approvals = approvals
        self.channels = channels
        self.clinic = clinic
        self.alert_doctor = alert_doctor
        self.clock = clock
        conn.executescript(SCHEMA)
        approvals.on_approve("visit_note", self._finalize_visit)
        approvals.on_approve("lab_explanation", self._send_explanation)

    # ----- patients -------------------------------------------------------

    def add_patient(self, name, phone, age=None, sex="", allergies="", conditions="",
                    language="English"):
        phone = "".join(c for c in phone if c.isdigit())
        if len(phone) == 10:
            phone = "91" + phone
        with self.conn:
            self.conn.execute(
                "INSERT INTO patients (name, phone, age, sex, allergies, conditions, language)"
                " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(phone) DO UPDATE SET"
                " name = excluded.name, age = excluded.age, sex = excluded.sex,"
                " allergies = excluded.allergies, conditions = excluded.conditions,"
                " language = excluded.language",
                (name, phone, age, sex, allergies, conditions, language))
        return self.patient(phone)

    def patient(self, key):
        col = "id" if isinstance(key, int) else "phone"
        if col == "phone":
            key = "".join(c for c in key if c.isdigit())
            key = "91" + key if len(key) == 10 else key
        r = self.conn.execute(f"SELECT * FROM patients WHERE {col} = ?", (key,)).fetchone()
        if r is None:
            raise ValueError(f"no patient {key}")
        return dict(r)

    def _context(self, p):
        return (f"Patient: {p['name']}, {p['age'] or '?'} y, {p['sex'] or '?'}\n"
                f"Known allergies: {p['allergies'] or 'none recorded'}\n"
                f"Known conditions: {p['conditions'] or 'none recorded'}\n"
                f"Patient's language: {p['language']}")

    # ----- 1: visit scribe ------------------------------------------------

    def draft_visit(self, phone, transcript):
        p = self.patient(phone)
        note = self.ai.ask_json(
            "medical.visit_note",
            f"You are a medical scribe at {self.clinic['clinic']}, India. Turn the "
            "consultation into a SOAP note and prescription for the doctor to review. Only "
            "write what the doctor said or examined; never add a diagnosis, medicine or "
            "test the doctor did not mention. Use generic medicine names with strength "
            "where stated. Patient instructions: in the patient's language, simple words, "
            "covering how to take each medicine and warning signs the doctor mentioned.",
            f"{self._context(p)}\n\nConsultation transcript:\n{transcript}",
            NOTE_SCHEMA, effort="high")
        warnings = prescription_warnings(note["medicines"], p["allergies"])
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO visits (patient_id, transcript, note, warnings, status, created_at)"
                " VALUES (?, ?, ?, ?, 'draft', ?)",
                (p["id"], transcript, json.dumps(note), json.dumps(warnings),
                 self.clock().isoformat()))
        visit_id = cur.lastrowid
        summary = f"Visit note for {p['name']}" + (f" - {len(warnings)} WARNING(S)"
                                                   if warnings else "")
        self.approvals.request("visit_note", summary,
                               {"visit_id": visit_id, "note": note, "warnings": warnings},
                               ref=visit_id)
        if any(w.startswith("ALLERGY") for w in warnings):
            self.alert_doctor(f"Allergy alert on draft prescription for {p['name']}: "
                              + "; ".join(warnings))
        return visit_id

    def _finalize_visit(self, payload):
        """Doctor approved (possibly edited) the note: send it and schedule reminders."""
        note = payload["note"]
        visit = self.conn.execute("SELECT * FROM visits WHERE id = ?",
                                  (payload["visit_id"],)).fetchone()
        p = self.patient(visit["patient_id"])
        with self.conn:
            self.conn.execute("UPDATE visits SET note = ?, status = 'approved' WHERE id = ?",
                              (json.dumps(note), visit["id"]))
        self.channels.send("whatsapp", p["phone"], prescription_text(self.clinic, p, note))
        self._schedule_reminders(p, note)

    def _schedule_reminders(self, p, note):
        today = self.clock().astimezone(IST).replace(minute=0, second=0, microsecond=0)
        rows = []
        for m in note["medicines"]:
            for day in range(m["duration_days"] or 0):
                for hour in DOSE_TIMES.get(m["frequency"], []):
                    at = (today + timedelta(days=day)).replace(hour=hour)
                    if at > self.clock():
                        rows.append((at, f"Reminder: {m['name']} {m['strength']}, {m['dose']} "
                                         f"now ({m['instructions'] or 'as advised'})."))
        if note["follow_up_days"]:
            visit_day = today + timedelta(days=note["follow_up_days"])
            rows.append((visit_day.replace(hour=10) - timedelta(days=1),
                         f"Reminder: your follow-up visit at {self.clinic['clinic']} is tomorrow. "
                         f"Reply to book a time. {self.clinic.get('phone', '')}".strip()))
        with self.conn:
            self.conn.executemany(
                "INSERT INTO reminders (patient_id, send_at, text) VALUES (?, ?, ?)",
                [(p["id"], at.isoformat(), text) for at, text in rows])

    # ----- 2: lab reports -------------------------------------------------

    def read_lab_report(self, phone, content):
        p = self.patient(phone)
        data = self.ai.ask_json(
            "medical.lab_read",
            "Read this lab report exactly as printed: every test, value, unit and the "
            "printed reference range.", content, LAB_SCHEMA)
        results = [dict(r, status=flag(r)) for r in data["results"]]
        critical = [r for r in results if r["status"] == "critical"]
        if critical:
            self.alert_doctor(f"CRITICAL lab values for {p['name']} ({p['phone']}): " + ", ".join(
                f"{r['test']} {r['value']:g} {r['unit']}" for r in critical))
        out = self.ai.ask_json(
            "medical.lab_explain",
            f"You explain lab reports to patients of {self.clinic['clinic']}. Write in the "
            "patient's language, in simple words, 6-10 short lines: what was tested, which "
            "values are outside the normal range and what that generally means. Do not "
            "diagnose, do not suggest medicines, and end by asking them to discuss the "
            "report with their doctor. If anything is critical, ask them to contact the "
            "clinic today.",
            f"{self._context(p)}\n\nResults (status computed by the clinic system): "
            f"{json.dumps(results)}",
            EXPLAIN_SCHEMA)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO reports (patient_id, results, explanation, status, created_at)"
                " VALUES (?, ?, ?, 'draft', ?)",
                (p["id"], json.dumps(results), out["explanation"], self.clock().isoformat()))
        abnormal = [r for r in results if r["status"] != "normal"]
        self.approvals.request(
            "lab_explanation",
            f"Lab report for {p['name']}: {len(abnormal)} abnormal, {len(critical)} critical",
            {"report_id": cur.lastrowid, "phone": p["phone"], "explanation": out["explanation"]},
            ref=cur.lastrowid)
        return cur.lastrowid, results

    def _send_explanation(self, payload):
        self.channels.send("whatsapp", payload["phone"], payload["explanation"])
        with self.conn:
            self.conn.execute("UPDATE reports SET status = 'sent', explanation = ? WHERE id = ?",
                              (payload["explanation"], payload["report_id"]))

    # ----- 3: reminders ---------------------------------------------------

    def send_due_reminders(self):
        """Run every 15 minutes from cron. Old missed reminders are skipped, not sent late."""
        at = self.clock()
        rows = self.conn.execute(
            "SELECT r.id, r.send_at, r.text, p.phone FROM reminders r"
            " JOIN patients p ON p.id = r.patient_id WHERE r.sent = 0").fetchall()
        sent = 0
        for r in rows:
            send_at = datetime.fromisoformat(r["send_at"])
            if send_at > at:
                continue
            if at - send_at < timedelta(hours=1):
                self.channels.send("whatsapp", r["phone"], r["text"])
                sent += 1
            with self.conn:
                self.conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (r["id"],))
        return sent


def prescription_text(clinic, patient, note):
    lines = [f"{clinic['clinic']} - Prescription for {patient['name']}",
             f"Dr. {clinic['doctor']}", ""]
    for i, m in enumerate(note["medicines"], 1):
        days = f" for {m['duration_days']} days" if m["duration_days"] else ""
        lines.append(f"{i}. {m['name']} {m['strength']} - {m['dose']} {m['frequency']}{days}"
                     f"{', ' + m['instructions'] if m['instructions'] else ''}")
    if note["tests_advised"]:
        lines += ["", "Tests: " + ", ".join(note["tests_advised"])]
    lines += ["", note["patient_instructions"]]
    if note["follow_up_days"]:
        lines.append(f"\nFollow-up after {note['follow_up_days']} days.")
    return "\n".join(lines)
