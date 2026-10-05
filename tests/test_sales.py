import json
import unittest
from datetime import datetime, timedelta, timezone

from axia.core.ai import AIError
from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import DryRun
from axia.core.calendar import IST
from axia.sales.agent import SalesAgent
from axia.sales.store import Store, normalize_phone

from .fakes import FakeAI

with open("examples/sales_playbook.json", encoding="utf-8") as f:
    PLAYBOOK = json.load(f)

QUALIFIED = {"score": 85, "fit_reasons": ["budget fits"], "risks": [],
             "disqualified": False, "angle": "3 BHK near office"}
OUTREACH = {"subject": "", "message": "Hi Amit, Neha from BuildRight here..."}


def reply(intent, slot="", follow="", human=False, text="Thanks!"):
    return {"intent": intent, "summary": intent, "chosen_slot": slot,
            "follow_up_date": follow, "needs_human": human, "reply": text}


class SalesAgentTest(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)  # Monday 11:30 IST
        conn = connect(":memory:")
        self.store = Store(conn, clock=lambda: self.time)
        self.channels = DryRun(out=lambda _: None)
        self.approvals = Approvals(conn, "sales")
        self.ai = FakeAI()
        self.alerts = []
        self.agent = SalesAgent(self.store, self.ai, Outbox(self.approvals, self.channels),
                                PLAYBOOK, self.alerts.append, clock=lambda: self.time)

    def add_contacted(self, **kw):
        lead, _ = self.store.add("Amit Shah", phone="98200 12345",
                                 message="Looking for 3 BHK in Baner", **kw)
        self.ai.queue("sales.qualify", QUALIFIED)
        self.ai.queue("sales.outreach", OUTREACH)
        self.agent.process_new()
        return self.store.get(lead.id)

    def test_new_lead_is_qualified_and_outreach_waits_for_approval(self):
        lead = self.add_contacted()
        self.assertEqual(lead.stage, "contacted")
        self.assertEqual(lead.score, 85)
        # Individual buyer without company or website: no web research step.
        self.assertEqual(self.ai.tasks(), ["sales.qualify", "sales.outreach"])
        pending = self.approvals.pending()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["payload"]["to"], "919820012345")
        self.assertEqual(self.channels.sent, [])
        self.approvals.approve(pending[0]["id"])
        self.assertEqual(self.channels.sent[0]["channel"], "whatsapp")

    def test_company_lead_is_researched_first(self):
        self.store.add("Ravi", email="ravi@acme.example", company="Acme Infotech")
        self.ai.queue("sales.research", "- 200 staff IT firm in Hinjewadi")
        self.ai.queue("sales.qualify", dict(QUALIFIED, score=30))
        self.agent.process_new()
        lead = self.store.find("ravi@acme.example")
        self.assertIn("Hinjewadi", lead.research)
        self.assertEqual(lead.stage, "nurture")  # below min score: no outreach yet
        self.assertIn("Hinjewadi", self.ai.calls[1]["content"])

    def test_disqualified_lead_gets_nothing(self):
        self.store.add("Renter", phone="9000000000")
        self.ai.queue("sales.qualify", dict(QUALIFIED, disqualified=True))
        self.agent.process_new()
        self.assertEqual(self.store.find("9000000000").stage, "disqualified")
        self.assertEqual(self.approvals.pending(), [])

    def test_ai_failure_leaves_lead_for_retry(self):
        self.store.add("Amit", phone="9000000001")
        self.ai.queue("sales.qualify", AIError("timeout"))
        self.agent.process_new()
        self.assertEqual(self.store.find("9000000001").stage, "new")

    def test_interested_reply_books_offered_slot_and_alerts_rep(self):
        lead = self.add_contacted()
        slot = self.agent.free_slots()[0]
        self.ai.queue("sales.reply", reply("interested", slot.isoformat(), text="Confirmed!"))
        lead = self.agent.handle_reply("+91 98200 12345", "Tuesday 10 am works")
        self.assertEqual(lead.stage, "meeting_booked")
        self.assertEqual(self.store.booked_slots(), {slot})
        self.assertIn("Meeting booked", self.alerts[0])
        self.assertNotIn(slot, self.agent.free_slots())

    def test_slot_not_offered_is_not_booked(self):
        self.add_contacted()
        made_up = datetime(2026, 10, 7, 3, 0, tzinfo=IST).isoformat()
        self.ai.queue("sales.reply", reply("interested", made_up))
        lead = self.agent.handle_reply("9820012345", "3 am?")
        self.assertEqual(lead.stage, "replied")
        self.assertEqual(self.store.booked_slots(), set())

    def test_price_negotiation_always_goes_to_a_human(self):
        self.agent.outbox.auto_send = True
        self.add_contacted()
        sent_before = len(self.channels.sent)
        self.ai.queue("sales.reply", reply("objection", human=True, text="Let me check"))
        self.agent.handle_reply("9820012345", "Can you do 65 lakh?")
        self.assertEqual(len(self.channels.sent), sent_before)
        self.assertEqual(len(self.approvals.pending()), 1)
        self.assertIn("Hot lead", self.alerts[-1])

    def test_not_now_and_unsubscribe(self):
        self.add_contacted()
        self.ai.queue("sales.reply", reply("not_now", follow="2026-12-01"))
        lead = self.agent.handle_reply("9820012345", "Call me in December")
        self.assertEqual(lead.stage, "nurture")
        self.assertEqual(lead.next_action_at.date().isoformat(), "2026-12-01")
        self.ai.queue("sales.reply", reply("unsubscribe", text=""))
        self.assertEqual(self.agent.handle_reply("9820012345", "STOP").stage, "opted_out")

    def test_unknown_sender_becomes_a_lead(self):
        self.ai.queue("sales.qualify", QUALIFIED)
        self.ai.queue("sales.outreach", OUTREACH)
        lead = self.agent.handle_reply("919811111111", "2 BHK Wakad price?")
        self.assertEqual(lead.stage, "contacted")
        self.assertEqual(lead.message, "2 BHK Wakad price?")

    def test_follow_ups_on_schedule_then_no_response(self):
        self.add_contacted()
        self.assertEqual(self.agent.run_followups(), 0)
        self.time += timedelta(days=2, minutes=1)
        self.ai.queue("sales.follow_up", OUTREACH)
        self.assertEqual(self.agent.run_followups(), 1)
        self.time += timedelta(days=2)
        self.assertEqual(self.agent.run_followups(), 0)  # second one is due after 5 days
        self.time += timedelta(days=3, minutes=1)
        self.ai.queue("sales.follow_up", OUTREACH)
        self.assertEqual(self.agent.run_followups(), 1)
        self.time += timedelta(days=30)
        self.agent.run_followups()
        self.assertEqual(self.store.find("9820012345").stage, "no_response")

    def test_free_slots_are_tomorrow_onward_within_hours(self):
        slots = self.agent.free_slots(4)
        self.assertEqual(len(slots), 4)
        for s in slots:
            local = s.astimezone(IST)
            self.assertGreater(local.date(), self.time.astimezone(IST).date())
            self.assertTrue(10 <= local.hour < 18)


class StoreTest(unittest.TestCase):
    def test_phone_normalizing_and_dedupe(self):
        self.assertEqual(normalize_phone("098200 12345"), "919820012345")
        store = Store(connect(":memory:"))
        a, new_a = store.add("A", phone="9820012345")
        b, new_b = store.add("A again", phone="+91-98200-12345", message="hello again")
        self.assertTrue(new_a)
        self.assertFalse(new_b)
        self.assertEqual(a.id, b.id)
        self.assertEqual(store.history(a.id)[0]["body"], "hello again")
        with self.assertRaises(ValueError):
            store.add("No contact")
