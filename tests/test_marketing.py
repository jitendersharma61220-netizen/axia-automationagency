import csv
import json
import os
import tempfile
import unittest
from datetime import date

from axia.core.approvals import Approvals, connect
from axia.marketing.engine import (MarketingEngine, channel_stats, check_content,
                                   limit_shift, read_metrics)

from .fakes import FakeAI

with open("examples/marketing_brand.json", encoding="utf-8") as f:
    BRAND = json.load(f)

PLAN = {
    "objective": "50 new members", "segments": ["office goers"],
    "offer": "Diwali: joining fee waived", "key_message": "Start before the sweets",
    "channel_mix": [{"channel": "instagram", "share": 40, "why": "reach"},
                    {"channel": "google_ads", "share": 60, "why": "intent"},
                    {"channel": "tiktok", "share": 10, "why": "not offered"}],
    "calendar": [{"day": "2026-10-20", "channel": "instagram", "theme": "Diwali prep"},
                 {"day": "2026-10-21", "channel": "google_ads", "theme": "Search"},
                 {"day": "2027-03-01", "channel": "instagram", "theme": "outside window"}],
    "kpis": [{"metric": "leads", "target": "150"}],
}
INSTA = {"caption": "Diwali ready?", "hashtags": ["#Indiranagar"], "visual_brief": "diya + dumbbell"}
ADS_OK = {"headlines": ["FitZone Indiranagar", "No Joining Fee", "Book a Free Trial"],
          "descriptions": ["Strength, Zumba and yoga near you."], "keywords": ["gym indiranagar"]}


class MarketingTest(unittest.TestCase):
    def setUp(self):
        conn = connect(":memory:")
        self.approvals = Approvals(conn, "marketing")
        self.ai = FakeAI({"marketing.research": "- Rival gym: 20% off", "marketing.plan": PLAN})
        self.engine = MarketingEngine(conn, self.ai, self.approvals, BRAND)
        self.cid = self.engine.plan("50 new members for Diwali", date(2026, 10, 15), 4)

    def test_plan_keeps_only_allowed_channels_and_dates(self):
        plan = self.engine.campaign(self.cid)["plan"]
        self.assertEqual([c["day"] for c in plan["calendar"]], ["2026-10-20", "2026-10-21"])
        self.assertEqual(plan["channel_mix"], {"instagram": 0.4, "google_ads": 0.6})
        self.assertIn("Rival gym", self.ai.calls[1]["content"])

    def test_content_is_checked_fixed_and_queued(self):
        too_long = dict(ADS_OK, headlines=["This headline is far too long for Google Ads"] * 3)
        self.ai.queue("marketing.content", INSTA, too_long, ADS_OK)
        self.assertEqual(self.engine.create_content(self.cid), 2)
        self.assertIn("over 30 characters", self.ai.calls[-1]["content"])
        pending = self.approvals.pending()
        self.assertEqual(len(pending), 2)
        # Re-running does not duplicate.
        self.assertEqual(self.engine.create_content(self.cid), 0)

    def test_only_approved_content_is_exported(self):
        self.ai.queue("marketing.content", INSTA, ADS_OK)
        self.engine.create_content(self.cid)
        first, second = self.approvals.pending()
        self.approvals.approve(first["id"], {"caption": "Edited caption"})
        self.approvals.reject(second["id"])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "cal.csv")
            self.assertEqual(self.engine.export(self.cid, out), 1)
            with open(out, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["text"], "Edited caption")

    def test_banned_phrases_caught(self):
        problems = check_content("whatsapp", {"message": "Guaranteed weight loss!",
                                              "call_to_action": "Reply YES"},
                                 BRAND["do_not_say"])
        self.assertTrue(problems)

    def test_analysis_numbers_and_safe_budget_shift(self):
        stats = channel_stats(read_metrics("examples/marketing_metrics.csv"))
        self.assertEqual(stats["google_ads"]["leads"], 66)
        self.assertEqual(stats["facebook"]["roas"], 0.75)
        self.ai.queue("marketing.analyze", {
            "summary": "Google works", "working": [], "not_working": [], "actions": [],
            "new_split": [{"channel": "instagram", "share": 0.0},
                          {"channel": "google_ads", "share": 1.0}]})
        a = self.engine.analyze(self.cid, "examples/marketing_metrics.csv")
        self.assertAlmostEqual(sum(a["new_split"].values()), 1, places=2)
        self.assertGreater(a["new_split"]["instagram"], 0.15)  # not cut to zero in one go

    def test_limit_shift(self):
        out = limit_shift({"a": 0.5, "b": 0.5}, {"a": 0.9, "b": 0.1})
        self.assertEqual(out, {"a": 0.7, "b": 0.3})
