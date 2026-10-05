"""The hiring agent: from a pile of resumes to booked interviews.

1. Read each resume (Claude: PDF, photo or text into structured data).
2. Score it against the job's requirements. Claude judges each requirement
   with evidence from the resume; code turns that into the score. Name,
   gender, age, photo and similar details are kept out of the scoring step.
3. Shortlist: candidates above the bar get the screening questions on
   WhatsApp; the rest get a polite regret (after HR approves it).
4. Screening: Claude grades the answers and pulls out notice period and
   expected salary; code checks them against the job's limits.
5. Interview: good candidates are offered real free slots; when they pick
   one, it is booked and the interviewer is told.
"""

import json
import re
from datetime import datetime

from axia.core import calendar
from axia.core.approvals import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    profile TEXT NOT NULL,
    assessment TEXT NOT NULL DEFAULT '{}',
    score INTEGER,
    screening TEXT NOT NULL DEFAULT '{}',
    stage TEXT NOT NULL,     -- new, screening, invited, interview_booked, rejected, withdrawn
    interview_at TEXT UNIQUE,
    created_at TEXT NOT NULL
);
"""

_S = {"type": "string"}
_STRS = {"type": "array", "items": _S}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


RESUME_SCHEMA = _obj(
    name=_S, phone=_S, email=_S, location=_S,
    total_experience_years={"type": "number"},
    roles=_STRS, skills=_STRS, education=_STRS, certifications=_STRS,
    summary={"type": "string", "description": "3 lines on the work they have done"},
)

ASSESS_SCHEMA = _obj(requirements={"type": "array", "items": _obj(
    requirement=_S,
    met={"type": "string", "enum": ["yes", "partial", "no"]},
    evidence={"type": "string", "description": "what in the resume shows it; empty if none"},
)})

SCREEN_SCHEMA = _obj(
    answers={"type": "array", "items": _obj(
        question=_S, score={"type": "integer", "description": "0-5"}, note=_S)},
    notice_period_days={"type": "integer", "description": "-1 if not stated"},
    expected_salary_lpa={"type": "number", "description": "lakh per annum; -1 if not stated"},
    withdrawn={"type": "boolean", "description": "candidate says they are not interested"},
)

SLOT_SCHEMA = _obj(chosen_slot=_S, reply=_S)

# Never shown to the scoring step.
PERSONAL = ("name", "phone", "email", "location")


def normalize_phone(phone):
    digits = re.sub(r"\D", "", phone or "")
    return "91" + digits if len(digits) == 10 else digits


class HiringAgent:
    def __init__(self, conn, ai, outbox, channels, job, alert, clock=now):
        self.conn = conn
        self.ai = ai
        self.outbox = outbox      # candidate messages (approval queue for regrets)
        self.channels = channels  # direct WhatsApp for screening conversations
        self.job = job
        self.alert = alert        # to the interviewer / HR
        self.clock = clock
        conn.executescript(SCHEMA)

    def _system(self, task):
        j = self.job
        return (f"You are a recruiter at {j['company']} hiring a {j['title']} "
                f"({j['location']}). Judge only skills, experience and evidence of work. "
                "Ignore name, gender, age, religion, caste, marital status, photos and "
                "college prestige.\n\nYour task now: " + task)

    # ----- 1-3: read, score, shortlist ------------------------------------

    def add_resume(self, content):
        profile = self.ai.ask_json(
            "hr.read_resume", "Read this resume exactly. Use empty values for anything missing.",
            content, RESUME_SCHEMA, effort="low")
        phone = normalize_phone(profile["phone"])
        if phone and self.conn.execute(
                "SELECT 1 FROM candidates WHERE phone = ?", (phone,)).fetchone():
            raise ValueError(f"{profile['name']} ({phone}) has already applied")
        work = {k: v for k, v in profile.items() if k not in PERSONAL}
        reqs = [f"MUST: {r}" for r in self.job["must_have"]] + \
               [f"NICE: {r}" for r in self.job.get("nice_to_have", [])]
        assessment = self.ai.ask_json(
            "hr.assess", self._system("Check the candidate against each requirement."),
            "Requirements:\n" + "\n".join(reqs) + f"\n\nCandidate:\n{json.dumps(work)}",
            ASSESS_SCHEMA)
        score, knocked_out = score_assessment(assessment, self.job)
        stage = "rejected" if knocked_out or score < self.job.get("min_score", 60) else "screening"
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO candidates (name, phone, email, profile, assessment, score, stage,"
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (profile["name"], phone, profile["email"].lower(), json.dumps(profile),
                 json.dumps(assessment), score, stage, self.clock().isoformat()))
        c = self.candidate(cur.lastrowid)
        if stage == "screening":
            self._send_screening(c)
        else:
            self._regret(c)
        return c

    def _send_screening(self, c):
        qs = "\n".join(f"{i}. {q}" for i, q in enumerate(self.job["screening_questions"], 1))
        text = (f"Hi {c['name'].split()[0]}, thank you for applying for {self.job['title']} at "
                f"{self.job['company']}. Your profile is shortlisted. Please reply to these "
                f"questions in one message:\n{qs}")
        self._message(c, text)

    def _regret(self, c):
        text = (f"Hi {c['name'].split()[0]}, thank you for applying for {self.job['title']} "
                f"at {self.job['company']}. We have decided to move ahead with other "
                "candidates for this role. We will keep your profile for future openings.")
        if c["phone"] or c["email"]:
            channel, to = ("whatsapp", c["phone"]) if c["phone"] else ("email", c["email"])
            self.outbox.send(channel, to, text, subject=f"Your application: {self.job['title']}",
                             ref=c["id"], why="regret", always_review=True)

    def _message(self, c, text):
        if c["phone"]:
            self.channels.send("whatsapp", c["phone"], text)
        elif c["email"]:
            self.channels.send("email", c["email"], text,
                               subject=f"{self.job['title']} at {self.job['company']}")

    # ----- 4-5: screening answers and interview booking -------------------

    def handle_reply(self, contact, text):
        c = self.find(contact)
        if c is None:
            raise ValueError(f"no candidate {contact}")
        if c["stage"] == "screening":
            return self._grade(c, text)
        if c["stage"] == "invited":
            return self._book(c, text)
        return c

    def _grade(self, c, text):
        g = self.ai.ask_json(
            "hr.screen", self._system("Grade the candidate's answers to the screening questions."),
            f"Questions: {json.dumps(self.job['screening_questions'])}\n\nTheir reply:\n{text}",
            SCREEN_SCHEMA)
        avg = (sum(a["score"] for a in g["answers"]) / len(g["answers"])) if g["answers"] else 0
        problems = []
        if g["withdrawn"]:
            return self._update(c, stage="withdrawn", screening=g)
        limit = self.job.get("max_salary_lpa")
        if limit and g["expected_salary_lpa"] > limit:
            problems.append(f"expects {g['expected_salary_lpa']:g} LPA (budget {limit:g})")
        notice = self.job.get("max_notice_days")
        if notice and g["notice_period_days"] > notice:
            problems.append(f"notice period {g['notice_period_days']} days (max {notice})")
        g["average"] = round(avg, 2)
        g["problems"] = problems
        if avg < self.job.get("min_screening_avg", 3) or problems:
            c = self._update(c, stage="rejected", screening=g)
            self._regret(c)
            return c
        slots = self.free_slots()
        self._message(c, f"Thank you! We'd like to invite you for an interview "
                         f"({self.job['interview']['minutes']} minutes, "
                         f"{self.job['interview']['mode']}). Which of these times works? "
                         f"{calendar.fmt(slots)}")
        return self._update(c, stage="invited", screening=g)

    def _book(self, c, text):
        slots = self.free_slots()
        r = self.ai.ask_json(
            "hr.pick_slot",
            "The candidate was offered interview slots. If they clearly chose one, copy it "
            "exactly into chosen_slot; otherwise leave it empty. Write a short friendly reply.",
            f"Offered: {[s.isoformat() for s in slots]}\nCandidate wrote: {text}",
            SLOT_SCHEMA, effort="low")
        slot = calendar.pick(r["chosen_slot"], slots)
        if slot is None:
            self._message(c, f"{r['reply']}\nAvailable: {calendar.fmt(slots)}")
            return c
        c = self._update(c, stage="interview_booked", interview_at=slot.isoformat())
        self._message(c, f"Confirmed: your interview for {self.job['title']} is on "
                         f"{calendar.fmt([slot])}. {self.job['interview'].get('details', '')}")
        self.alert(f"Interview booked: {c['name']} ({c['score']}/100) on {calendar.fmt([slot])}")
        return c

    def free_slots(self, count=3):
        booked = {r["interview_at"] for r in self.conn.execute(
            "SELECT interview_at FROM candidates WHERE interview_at IS NOT NULL")}
        return calendar.free_slots(self.clock(), self.job["interview"],
                                   {datetime.fromisoformat(b) for b in booked}, count)

    # ----- storage --------------------------------------------------------

    def _update(self, c, **fields):
        if "screening" in fields:
            fields["screening"] = json.dumps(fields["screening"])
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.conn:
            self.conn.execute(f"UPDATE candidates SET {sets} WHERE id = ?",
                              (*fields.values(), c["id"]))
        return self.candidate(c["id"])

    def candidate(self, cid):
        r = self.conn.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
        return dict(r) if r else None

    def find(self, contact):
        if "@" in contact:
            r = self.conn.execute("SELECT * FROM candidates WHERE email = ?",
                                  (contact.strip().lower(),)).fetchone()
        else:
            r = self.conn.execute("SELECT * FROM candidates WHERE phone = ?",
                                  (normalize_phone(contact),)).fetchone()
        return dict(r) if r else None

    def ranking(self):
        rows = self.conn.execute("SELECT * FROM candidates ORDER BY score DESC, id")
        return [dict(r) for r in rows]


def score_assessment(assessment, job):
    """Must-haves are 70% of the score, nice-to-haves 30%. A clear 'no' on a
    must-have listed in job["knockout"] rejects the candidate outright."""
    points = {"yes": 1.0, "partial": 0.5, "no": 0.0}
    must, nice, knocked_out = [], [], False
    knockouts = [k.lower() for k in job.get("knockout", [])]
    for r in assessment["requirements"]:
        text = r["requirement"]
        value = points[r["met"]]
        if text.upper().startswith("NICE"):
            nice.append(value)
        else:
            must.append(value)
            if r["met"] == "no" and any(k in text.lower() for k in knockouts):
                knocked_out = True
    must_part = sum(must) / len(must) if must else 1.0
    nice_part = sum(nice) / len(nice) if nice else must_part
    return round(100 * (0.7 * must_part + 0.3 * nice_part)), knocked_out
