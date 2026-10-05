import json
import unittest
from datetime import datetime, timedelta, timezone

from axia.core.approvals import Approvals, connect
from axia.core.channels import DryRun
from axia.medical.agent import ClinicAssistant, flag, prescription_warnings

from .fakes import FakeAI

with open("examples/clinic.json", encoding="utf-8") as f:
    CLINIC = json.load(f)


def med(name, freq="TDS", days=5, dose="1 tablet"):
    return {"name": name, "strength": "500 mg", "dose": dose, "frequency": freq,
            "duration_days": days, "instructions": "after food"}


NOTE = {"subjective": "Fever 3 days, sore throat", "objective": "T 101.2F, tonsils swollen",
        "assessment": "Acute tonsillitis", "plan": "Antibiotic, antipyretic, gargles",
        "medicines": [med("Amoxicillin"), med("Paracetamol", freq="SOS", days=0)],
        "tests_advised": [], "follow_up_days": 5,
        "patient_instructions": "Dawai khana khane ke baad lein."}

LAB = {"results": [
    {"test": "Hemoglobin", "value": 6.2, "unit": "g/dL", "low": 13, "high": 17},
    {"test": "Fasting Glucose", "value": 132, "unit": "mg/dL", "low": 70, "high": 100},
    {"test": "TSH", "value": 2.1, "unit": "mIU/L", "low": 0.4, "high": 4.0},
]}


class SafetyChecksTest(unittest.TestCase):
    def test_allergy_group_is_caught(self):
        w = prescription_warnings([med("Amoxicillin")], "Penicillin")
        self.assertTrue(w[0].startswith("ALLERGY"))
        self.assertEqual(prescription_warnings([med("Amoxicillin")], ""), [])

    def test_missing_fields_and_duplicates(self):
        w = prescription_warnings([med("Cefixime", days=0), med("Cefixime 200")], "")
        self.assertIn("Cefixime: missing duration", w)
        self.assertIn("cefixime is prescribed more than once", w)

    def test_flags_are_recomputed(self):
        self.assertEqual(flag(LAB["results"][0]), "critical")
        self.assertEqual(flag(LAB["results"][1]), "high")
        self.assertEqual(flag(LAB["results"][2]), "normal")


class ClinicAssistantTest(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 5, 4, 0, tzinfo=timezone.utc)  # 9:30 am IST
        conn = connect(":memory:")
        self.channels = DryRun(out=lambda _: None)
        self.approvals = Approvals(conn, "medical")
        self.ai = FakeAI()
        self.alerts = []
        self.clinic = ClinicAssistant(conn, self.ai, self.approvals, self.channels, CLINIC,
                                      self.alerts.append, clock=lambda: self.time)
        self.clinic.add_patient("Ramesh Kumar", "98450 00000", 45, "M", language="Hinglish")

    def test_visit_note_waits_for_doctor_then_sends_and_schedules(self):
        self.ai.queue("medical.visit_note", NOTE)
        self.clinic.draft_visit("9845000000", "transcript")
        self.assertEqual(self.channels.sent, [])
        item = self.approvals.pending()[0]
        self.approvals.approve(item["id"])
        rx = self.channels.sent[0]
        self.assertEqual(rx["to"], "919845000000")
        self.assertIn("Amoxicillin 500 mg - 1 tablet TDS for 5 days", rx["body"])
        # Day 1 doses after 9:30 am (2 pm, 8 pm) + 4 full days x 3 + follow-up reminder.
        count = self.clinic.conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0]
        self.assertEqual(count, 2 + 4 * 3 + 1)

    def test_allergy_alerts_doctor_immediately(self):
        self.clinic.add_patient("Ramesh Kumar", "9845000000", 45, "M", allergies="penicillin")
        self.ai.queue("medical.visit_note", NOTE)
        self.clinic.draft_visit("9845000000", "transcript")
        self.assertIn("Allergy alert", self.alerts[0])
        self.assertIn("WARNING", self.approvals.pending()[0]["summary"])

    def test_lab_report_critical_alert_and_approval(self):
        self.ai.queue("medical.lab_read", LAB)
        self.ai.queue("medical.lab_explain", {"explanation": "Aapka hemoglobin bahut kam hai..."})
        _, results = self.clinic.read_lab_report("9845000000", "report text")
        self.assertIn("CRITICAL", self.alerts[0])
        self.assertIn('"status": "critical"', self.ai.calls[1]["content"])
        self.assertEqual(self.channels.sent, [])
        self.approvals.approve(self.approvals.pending()[0]["id"])
        self.assertIn("hemoglobin", self.channels.sent[0]["body"])

    def test_reminders_sent_once_and_stale_ones_skipped(self):
        self.ai.queue("medical.visit_note", NOTE)
        self.clinic.draft_visit("9845000000", "t")
        self.approvals.approve(self.approvals.pending()[0]["id"])
        self.channels.sent.clear()
        self.time += timedelta(hours=4, minutes=35)  # 2:05 pm IST
        self.assertEqual(self.clinic.send_due_reminders(), 1)
        self.assertEqual(self.clinic.send_due_reminders(), 0)
        self.time += timedelta(days=2)  # server was down: old doses are not sent late
        self.assertLessEqual(self.clinic.send_due_reminders(), 1)
