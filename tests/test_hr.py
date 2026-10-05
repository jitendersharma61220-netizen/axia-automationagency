import json
import unittest
from datetime import datetime, timezone

from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import DryRun
from axia.hr.agent import HiringAgent, score_assessment

from .fakes import FakeAI

with open("examples/job.json", encoding="utf-8") as f:
    JOB = json.load(f)

PROFILE = {"name": "Pooja Verma", "phone": "98110 22334", "email": "pooja.verma@example.com",
           "location": "Pitampura, Delhi", "total_experience_years": 5,
           "roles": ["Lab Technician"], "skills": ["Sysmex XN-550"],
           "education": ["B.Sc. MLT"], "certifications": [], "summary": "..."}


def assess(*mets):
    reqs = [f"MUST: {r}" for r in JOB["must_have"]] + [f"NICE: {r}" for r in JOB["nice_to_have"]]
    return {"requirements": [{"requirement": r, "met": m, "evidence": ""}
                             for r, m in zip(reqs, mets)]}


GOOD = assess("yes", "yes", "yes", "yes", "yes", "partial")
NO_DEGREE = assess("no", "yes", "yes", "yes", "yes", "yes")


def screening(salary=4.0, notice=30, score=4, withdrawn=False):
    return {"answers": [{"question": q, "score": score, "note": ""}
                        for q in JOB["screening_questions"]],
            "notice_period_days": notice, "expected_salary_lpa": salary, "withdrawn": withdrawn}


class ScoringTest(unittest.TestCase):
    def test_score_and_knockout(self):
        self.assertEqual(score_assessment(GOOD, JOB), (95, False))
        score, out = score_assessment(NO_DEGREE, JOB)
        self.assertTrue(out)


class HiringAgentTest(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 5, 6, 0, tzinfo=timezone.utc)
        conn = connect(":memory:")
        self.channels = DryRun(out=lambda _: None)
        self.approvals = Approvals(conn, "hr")
        self.ai = FakeAI()
        self.alerts = []
        self.agent = HiringAgent(conn, self.ai, Outbox(self.approvals, self.channels),
                                 self.channels, JOB, self.alerts.append, clock=lambda: self.time)

    def apply(self, assessment=GOOD, profile=PROFILE):
        self.ai.queue("hr.read_resume", profile)
        self.ai.queue("hr.assess", assessment)
        return self.agent.add_resume("resume text")

    def test_scoring_never_sees_personal_details(self):
        self.apply()
        scoring_input = self.ai.calls[1]["content"]
        for private in ("Pooja", "98110", "pooja.verma", "Pitampura"):
            self.assertNotIn(private, scoring_input)

    def test_shortlisted_candidate_gets_questions_then_interview(self):
        c = self.apply()
        self.assertEqual(c["stage"], "screening")
        self.assertIn("analysers", self.channels.sent[0]["body"])
        self.ai.queue("hr.screen", screening())
        c = self.agent.handle_reply("9811022334", "answers...")
        self.assertEqual(c["stage"], "invited")
        slot = self.agent.free_slots()[1]
        self.ai.queue("hr.pick_slot", {"chosen_slot": slot.isoformat(), "reply": "Great"})
        c = self.agent.handle_reply("9811022334", "Wednesday works")
        self.assertEqual(c["stage"], "interview_booked")
        self.assertIn("Interview booked", self.alerts[0])
        self.assertNotIn(slot, self.agent.free_slots())

    def test_unclear_slot_reply_offers_slots_again(self):
        self.apply()
        self.ai.queue("hr.screen", screening())
        self.agent.handle_reply("9811022334", "answers")
        self.ai.queue("hr.pick_slot", {"chosen_slot": "", "reply": "Which day suits you?"})
        c = self.agent.handle_reply("9811022334", "any time")
        self.assertEqual(c["stage"], "invited")
        self.assertIn("Available:", self.channels.sent[-1]["body"])

    def test_salary_over_budget_is_rejected_with_reviewed_regret(self):
        self.apply()
        self.ai.queue("hr.screen", screening(salary=6.5))
        c = self.agent.handle_reply("9811022334", "answers")
        self.assertEqual(c["stage"], "rejected")
        self.assertIn("6.5 LPA", c["screening"])
        self.assertEqual(len(self.approvals.pending()), 1)  # regret waits for HR

    def test_knockout_and_duplicate(self):
        c = self.apply(NO_DEGREE)
        self.assertEqual(c["stage"], "rejected")
        self.assertEqual(len(self.approvals.pending()), 1)
        self.ai.queue("hr.read_resume", PROFILE)
        with self.assertRaises(ValueError):
            self.agent.add_resume("same person again")
