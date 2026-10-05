import json
import unittest
from datetime import datetime, timezone

from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import DryRun
from axia.ops.agent import OpsAgent, load_purchase_orders
from axia.ops.checks import check_bill, gstin_valid

from .fakes import FakeAI

with open("examples/ops_company.json", encoding="utf-8") as f:
    COMPANY = json.load(f)
OUR_GSTIN = COMPANY["gstin"]

ELECTRICAL = {  # what Claude reads from examples/bill_electricity.txt
    "vendor": "Sharma Electricals & Supplies", "vendor_gstin": "07ABCDE1234F1Z2",
    "buyer_gstin": OUR_GSTIN, "invoice_number": "SE/2026/0457", "invoice_date": "2026-10-03",
    "due_date": "", "payment_terms_days": 15, "po_number": "PO-1042",
    "lines": [{"description": "LED tube light 20W", "quantity": 4, "rate": 400, "amount": 1600},
              {"description": "Extension board", "quantity": 1, "rate": 450, "amount": 450}],
    "taxable_value": 2050, "cgst": 184.5, "sgst": 184.5, "igst": 0, "total": 2419,
}
MEDILAB = {  # examples/bill_medilab.txt: rate above PO, more billed than received
    "vendor": "Medilab Consumables", "vendor_gstin": "06BBBCD4321E1Z7",
    "buyer_gstin": OUR_GSTIN, "invoice_number": "ML-88213", "invoice_date": "2026-09-28",
    "due_date": "2026-10-28", "payment_terms_days": 0, "po_number": "PO-1043",
    "lines": [{"description": "Vacutainer tubes (box of 100)", "quantity": 20, "rate": 890,
               "amount": 17800},
              {"description": "Nitrile gloves (box of 100)", "quantity": 30, "rate": 320,
               "amount": 9600}],
    "taxable_value": 27400, "cgst": 0, "sgst": 0, "igst": 3288, "total": 30688,
}
SAME_ORDER = {"matches": [{"bill_line": 0, "po_line": 0}, {"bill_line": 1, "po_line": 1}]}
REVIEW = {"approver_note": "Rate is Rs 40 above PO and 5 boxes not received.",
          "vendor_email_subject": "Query on ML-88213", "vendor_email": "Dear team, ..."}


class ChecksTest(unittest.TestCase):
    def test_gstin_check_digit(self):
        self.assertTrue(gstin_valid("07ABCDE1234F1Z2"))
        self.assertFalse(gstin_valid("07ABCDE1234F1Z3"))
        self.assertFalse(gstin_valid("07ABCDE1234"))

    def test_clean_bill_passes(self):
        self.assertEqual(check_bill(ELECTRICAL, OUR_GSTIN), [])

    def test_wrong_tax_type_and_bad_math(self):
        bad = dict(ELECTRICAL, cgst=0, sgst=0, igst=369, total=2500)
        issues = " ".join(check_bill(bad, OUR_GSTIN))
        self.assertIn("IGST charged on a same-state purchase", issues)
        self.assertIn("bill total is 2500.00", issues)


class OpsAgentTest(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
        conn = connect(":memory:")
        self.channels = DryRun(out=lambda _: None)
        self.approvals = Approvals(conn, "ops")
        self.ai = FakeAI()
        self.alerts = []
        self.agent = OpsAgent(conn, self.ai, self.approvals, Outbox(self.approvals, self.channels),
                              COMPANY, load_purchase_orders("examples/purchase_orders.csv"),
                              self.alerts.append, clock=lambda: self.time)

    def run_bill(self, bill, match=SAME_ORDER, review=REVIEW):
        self.ai.queue("ops.extract", bill)
        self.ai.queue("ops.match", match)
        if review:
            self.ai.queue("ops.review", review)
        return self.agent.process("bill.txt", "bill text")

    def test_clean_small_bill_is_auto_approved_with_due_date(self):
        b = self.run_bill(ELECTRICAL, review=None)
        self.assertEqual(b["status"], "approved")
        self.assertEqual(b["due_date"], "2026-10-18")  # invoice date + 15 days
        self.assertEqual(self.alerts, [])

    def test_po_mismatch_is_held_with_note_and_vendor_query(self):
        b = self.run_bill(MEDILAB)
        self.assertEqual(b["status"], "on_hold")
        issues = " ".join(json.loads(b["issues"]))
        self.assertIn("billed at 890.00, PO rate is 850.00", issues)
        self.assertIn("received only 15", issues)
        kinds = sorted(i["kind"] for i in self.approvals.pending())
        self.assertEqual(kinds, ["bill", "message"])  # bill approval + vendor email draft
        self.assertIn("Bill on hold", self.alerts[0])
        self.assertEqual(self.channels.sent, [])  # vendor email waits for a human

    def test_approve_and_reject_held_bills(self):
        b = self.run_bill(MEDILAB)
        bill_item = next(i for i in self.approvals.pending() if i["kind"] == "bill")
        self.approvals.approve(bill_item["id"])
        self.assertEqual(self.agent.bill(b["id"])["status"], "approved")

    def test_duplicate_bill(self):
        self.run_bill(ELECTRICAL, review=None)
        self.ai.queue("ops.extract", ELECTRICAL)
        self.assertEqual(self.agent.process("again.txt", "x")["status"], "duplicate")

    def test_unmatched_line_and_missing_po(self):
        b = self.run_bill(MEDILAB, match={"matches": [{"bill_line": 0, "po_line": -1},
                                                      {"bill_line": 1, "po_line": 1}]})
        self.assertIn("not on the purchase order", b["issues"])
        self.ai.queue("ops.extract", dict(ELECTRICAL, po_number="", invoice_number="X1"))
        self.ai.queue("ops.review", REVIEW)
        b2 = self.agent.process("nopo.txt", "x")
        self.assertIn("No purchase order found", b2["issues"])

    def test_payables_and_ledger(self):
        self.run_bill(ELECTRICAL, review=None)
        due = self.agent.payables(7)
        self.assertEqual(len(due), 1)
        self.assertTrue(due[0]["overdue"])
        self.agent.mark_paid(due[0]["id"])
        self.assertEqual(self.agent.payables(7), [])
