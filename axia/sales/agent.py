"""The AI sales agent (SDR): research, qualify, reach out, handle replies, book.

Each lead moves through the pipeline in steps. Claude does the thinking in
each step and returns structured data; this code decides what happens next,
so nothing is sent or booked outside the rules in the playbook. Messages go
through the approval queue unless the playbook sets "auto_send".
"""

import json
from datetime import datetime, timedelta

from axia.core import calendar
from axia.core.ai import AIError
from axia.core.calendar import IST
from axia.core.approvals import now


QUALIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "description": "0-100 fit with the ideal customer"},
        "fit_reasons": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "disqualified": {"type": "boolean"},
        "angle": {"type": "string", "description": "what to lead with in outreach"},
    },
    "required": ["score", "fit_reasons", "risks", "disqualified", "angle"],
    "additionalProperties": False,
}

MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "description": "email subject; empty for WhatsApp"},
        "message": {"type": "string"},
    },
    "required": ["subject", "message"],
    "additionalProperties": False,
}

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": [
            "interested", "question", "objection", "not_now", "not_interested",
            "unsubscribe", "other"]},
        "summary": {"type": "string"},
        "chosen_slot": {"type": "string",
                        "description": "exactly one of the offered slots, or empty"},
        "follow_up_date": {"type": "string", "description": "YYYY-MM-DD, or empty"},
        "needs_human": {"type": "boolean",
                        "description": "true for pricing negotiation, complaints, or anything "
                                       "the playbook does not cover"},
        "reply": {"type": "string", "description": "message to send back; empty for unsubscribe"},
    },
    "required": ["intent", "summary", "chosen_slot", "follow_up_date", "needs_human", "reply"],
    "additionalProperties": False,
}


class SalesAgent:
    def __init__(self, store, ai, outbox, playbook, alert, clock=now):
        self.store = store
        self.ai = ai
        self.outbox = outbox
        self.pb = playbook
        self.alert = alert  # function(text): message to the sales rep
        self.clock = clock

    # ----- shared context -------------------------------------------------

    def _system(self, role):
        pb = self.pb
        return (
            f"You are the sales assistant for {pb['company']}. {pb['about']}\n"
            f"Offer: {pb['offer']}\nIdeal customer: {pb['ideal_customer']}\n"
            f"Disqualify if: {pb.get('disqualify_if', 'n/a')}\n"
            f"Pricing notes: {pb.get('pricing_notes', 'n/a')}\nTone: {pb.get('tone', '')}\n"
            "Never invent facts, prices, discounts or availability that are not given here.\n\n"
            f"Your task now: {role}"
        )

    def profile(self, p):
        lines = [f"Name: {p.name}", f"Company: {p.company or '-'}", f"Website: {p.website or '-'}",
                 f"Source: {p.source}", f"Their enquiry: {p.message or '-'}"]
        if p.research:
            lines.append(f"Research notes:\n{p.research}")
        if p.qualification:
            lines.append(f"Qualification: {json.dumps(p.qualification)}")
        history = self.store.history(p.id)
        if history:
            lines.append("Conversation so far:")
            lines += [f"  [{h['kind']} {h['channel']} {h['at'][:16]}] {h['body']}" for h in history]
        return "\n".join(lines)

    def _channel(self, p):
        if p.phone and (self.pb.get("prefer_whatsapp") or not p.email):
            return "whatsapp", p.phone
        return "email", p.email

    def _send(self, p, subject, body, why, review=False):
        channel, to = self._channel(p)
        self.outbox.send(channel, to, body, subject=subject if channel == "email" else "",
                         ref=p.id, why=why, always_review=review)

    # ----- pipeline steps -------------------------------------------------

    def process_new(self):
        """Research, qualify and write first outreach for every new lead."""
        done = 0
        for p in self.store.in_stage("new"):
            try:
                self.research(p)
                p = self.qualify(self.store.get(p.id))
                if p.stage == "qualified":
                    self.outreach(p)
                done += 1
            except AIError as e:
                print(f"Lead #{p.id} {p.name}: AI step failed, will retry on the next run: {e}")
                self.store.log(p.id, "note", "", f"AI step failed, will retry: {e}")
        return done

    def research(self, p):
        if not (p.company or p.website):
            return p  # an individual buyer: the enquiry itself is the research
        notes = self.ai.research(
            "sales.research",
            self._system("Research this lead on the web before we contact them."),
            f"{self.profile(p)}\n\nFind what this company or person does, size, location, "
            "and any recent news that relates to our offer. Write 3-6 short factual bullet "
            "points and say if you could not find something. No guesses.")
        return self.store.update(p.id, research=notes)

    def qualify(self, p):
        q = self.ai.ask_json(
            "sales.qualify",
            self._system("Score how well this lead fits our ideal customer."),
            self.profile(p), QUALIFY_SCHEMA)
        score = max(0, min(100, int(q["score"])))
        if q["disqualified"]:
            stage = "disqualified"
        elif score >= self.pb.get("min_score", 50):
            stage = "qualified"
        else:
            stage = "nurture"
            q["note"] = "below min score"
        return self.store.update(p.id, score=score, qualification=q, stage=stage,
                                 next_action_at=self.clock() + timedelta(days=30)
                                 if stage == "nurture" else None)

    def outreach(self, p):
        channel, _ = self._channel(p)
        slots = self.free_slots()
        m = self.ai.ask_json(
            "sales.outreach",
            self._system(f"Write the first {channel} message to this lead."),
            f"{self.profile(p)}\n\nUse the angle from qualification. Offer a "
            f"{self.pb['meeting']['what']} at one of these times: {calendar.fmt(slots)}. "
            f"Keep it under {90 if channel == 'whatsapp' else 150} words, sign as "
            f"{self.pb['sales_rep']['name']} from {self.pb['company']}.",
            MESSAGE_SCHEMA)
        self._send(p, m["subject"], m["message"], "first outreach")
        self.store.log(p.id, "out", channel, m["message"])
        return self.store.update(p.id, stage="contacted", followups_sent=0)

    def handle_reply(self, contact, text, channel="whatsapp"):
        """A lead wrote back. Understand it and take the next step."""
        p = self.store.find(contact)
        if p is None:
            # Someone new messaged us first: they become a lead straight away.
            p, _ = self.store.add(name="New enquiry", phone=contact if "@" not in contact else "",
                                  email=contact if "@" in contact else "",
                                  message=text, source=channel)
            self.process_new()
            return self.store.get(p.id)
        self.store.log(p.id, "in", channel, text)
        slots = self.free_slots()
        r = self.ai.ask_json(
            "sales.reply",
            self._system("Read the lead's latest message, classify it, and draft our reply."),
            f"{self.profile(p)}\n\nOffered slots (copy one exactly into chosen_slot if the "
            f"lead clearly agreed to it): {[s.isoformat() for s in slots]}\n"
            f"Today is {self.clock().astimezone(IST):%Y-%m-%d}.",
            REPLY_SCHEMA)
        intent = r["intent"]
        note = f"{intent}: {r['summary']}"
        self.store.log(p.id, "note", "", note)

        if intent == "unsubscribe":
            return self.store.update(p.id, stage="opted_out")
        if intent == "not_interested":
            if r["reply"]:
                self._send(p, "", r["reply"], "polite close")
            return self.store.update(p.id, stage="lost")
        if intent == "not_now":
            follow = self._date(r["follow_up_date"]) or self.clock() + timedelta(days=30)
            if r["reply"]:
                self._send(p, "", r["reply"], "not now")
            return self.store.update(p.id, stage="nurture", next_action_at=follow)

        slot = calendar.pick(r["chosen_slot"], slots)
        if intent == "interested" and slot and self.store.book(p.id, slot):
            self._send(p, "Your visit is confirmed", r["reply"], "booking confirmation")
            self.alert(f"Meeting booked: {p.name} ({p.company or p.phone or p.email}) on "
                       f"{calendar.fmt([slot])}. Score {p.score}. {r['summary']}")
            return self.store.update(p.id, stage="meeting_booked")
        # Questions, objections, or interest without a time: answer and offer slots.
        self._send(p, "Re: your enquiry", r["reply"], intent, review=r["needs_human"])
        if r["needs_human"] or (p.score or 0) >= 80:
            self.alert(f"Hot lead needs you: {p.name} ({p.phone or p.email}). {note}")
        return self.store.update(p.id, stage="replied")

    def run_followups(self):
        """Follow up on silence, and wake up leads whose nurture date has come."""
        at = self.clock()
        days = self.pb.get("follow_up_days", [2, 5])
        sent = 0
        for p in self.store.in_stage("contacted"):
            last_in = self.store.last_activity(p.id, "in")
            last_out = self.store.last_activity(p.id, "out") or p.created_at
            if last_in and last_in > last_out:
                continue  # their reply is being handled
            if p.followups_sent >= len(days):
                self.store.update(p.id, stage="no_response")
                continue
            if at - last_out < timedelta(days=days[p.followups_sent]):
                continue
            if self._follow_up(p, "They have not replied. Write a short, friendly follow-up "
                                  "that adds one new useful point; do not repeat the first message."):
                self.store.update(p.id, followups_sent=p.followups_sent + 1)
                sent += 1
        for p in self.store.in_stage("nurture"):
            if p.next_action_at and p.next_action_at <= at:
                if self._follow_up(p, "Re-open the conversation they asked us to come back to."):
                    self.store.update(p.id, stage="contacted", followups_sent=0)
                    sent += 1
        return sent

    def _follow_up(self, p, instruction):
        channel, _ = self._channel(p)
        try:
            m = self.ai.ask_json("sales.follow_up", self._system(instruction),
                                 f"{self.profile(p)}\n\nFree slots: {calendar.fmt(self.free_slots())}",
                                 MESSAGE_SCHEMA)
        except AIError as e:
            self.store.log(p.id, "note", "", f"follow-up failed, will retry: {e}")
            return False
        self._send(p, m["subject"], m["message"], "follow-up")
        self.store.log(p.id, "out", channel, m["message"])
        return True

    # ----- calendar -------------------------------------------------------

    def free_slots(self, count=3):
        return calendar.free_slots(self.clock(), self.pb["meeting"], self.store.booked_slots(),
                                   count)

    @staticmethod
    def _date(text):
        try:
            return datetime.strptime(text, "%Y-%m-%d").replace(hour=10, tzinfo=IST)
        except ValueError:
            return None

    # ----- reporting ------------------------------------------------------

    def report(self):
        counts = {}
        for p in self.store.all():
            counts[p.stage] = counts.get(p.stage, 0) + 1
        hot = [p for p in self.store.all() if (p.score or 0) >= 80
               and p.stage in ("contacted", "replied")]
        return {"stages": counts, "meetings": self.store.meetings(),
                "hot_leads": [(p.name, p.score, p.stage) for p in hot]}

