import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

os.environ["AXIA_DATA_DIR"] = tempfile.mkdtemp()
for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
    os.environ.pop(var, None)

from axia_engine import core, deck, generator, intake, roi, server, whatsapp  # noqa: E402

FORM = {
    "service": "whatsapp",
    "name": "Maria",
    "business_name": "Casa Verde Furniture",
    "industry": "Furniture store",
    "country": "Spain",
    "whatsapp": "+34 612 345 678",
    "business_description": "We sell handmade furniture online and in one showroom.",
    "main_problem": "We get 80 WhatsApp messages a day and reply hours late.",
    "currency": "EUR",
    "team_size": "4",
    "monthly_inquiries": "1200",
    "avg_order_value": "450",
    "hours_per_week": "25",
    "hourly_cost": "18",
    "conversion_pct": "8",
    "margin_pct": "35",
}


class IntakeTest(unittest.TestCase):
    def test_parses_and_normalises(self):
        i = intake.parse(FORM)
        self.assertEqual(i["whatsapp"], "34612345678")
        self.assertEqual(i["monthly_inquiries"], 1200)

    def test_rejects_bad_input(self):
        for bad in ({**FORM, "service": "x"}, {**FORM, "whatsapp": "12"}, {**FORM, "main_problem": " "}, {**FORM, "hourly_cost": "abc"}, {**FORM, "margin_pct": "500"}):
            with self.assertRaises(intake.IntakeError):
                intake.parse(bad)


class RoiTest(unittest.TestCase):
    def test_numbers(self):
        n = roi.estimate(intake.parse(FORM))
        # 25 h/week * 52/12 * 0.6 = 65 h; 65 * 18 = 1170
        self.assertEqual(n["hours_saved_month"], 65)
        self.assertEqual(n["labour_saving_month"], 1170)
        # 1200 * 8% * 25% = 24 customers * 450 = 10800 revenue, 35% = 3780 profit
        self.assertEqual(n["extra_revenue_month"], 10800)
        self.assertEqual(n["extra_profit_month"], 3780)
        self.assertEqual(n["yearly_gain"], (1170 + 3780) * 12)
        self.assertEqual(n["display"]["monthly_gain"], "€4,950")

    def test_inr_grouping(self):
        self.assertEqual(roi.money(1234567, "INR"), "₹12,34,567")
        self.assertEqual(roi.money(999, "INR"), "₹999")


class BrandTest(unittest.TestCase):
    def test_removes_ai(self):
        out = generator._brand_safe({"a": ["Our AI-powered desk", "AI replies fast", "Thai food"]})
        self.assertEqual(out["a"], ["Our automated desk", "automation replies fast", "Thai food"])


class GeneratorTest(unittest.TestCase):
    def test_template_without_key(self):
        i = intake.parse(FORM)
        content, source = generator.generate(i, roi.estimate(i))
        self.assertEqual(source, "template")
        self.assertIn("Casa Verde Furniture", content["headline"])
        self.assertGreaterEqual(len(content["demo"]["messages"]), 5)

    def test_falls_back_when_claude_fails(self):
        i = intake.parse(FORM)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}), mock.patch.object(generator, "_with_claude", side_effect=RuntimeError("down")):
            _, source = generator.generate(i, roi.estimate(i))
        self.assertEqual(source, "template")

    def test_claude_output_is_brand_safe(self):
        i = intake.parse(FORM)
        fake = generator._with_template(i, roi.estimate(i))
        fake["headline"] = "AI desk for Casa Verde"
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "x"}), mock.patch.object(generator, "_with_claude", return_value=fake):
            content, source = generator.generate(i, roi.estimate(i))
        self.assertEqual(source, "claude")
        self.assertEqual(content["headline"], "automation desk for Casa Verde")


class WhatsAppTest(unittest.TestCase):
    def test_links_without_credentials(self):
        p = core.build(FORM, "https://site.example", "https://api.example")
        self.assertFalse(p["whatsapp"]["sent"])
        self.assertTrue(p["whatsapp"]["save_link"].startswith("https://wa.me/34612345678?text="))
        self.assertIn("€4,950", p["whatsapp"]["text"])
        self.assertIn("plan.html?id=" + p["id"] + "&engine=https%3A%2F%2Fapi.example", p["proposal_url"])

    def test_template_payload(self):
        with mock.patch.dict(os.environ, {"WHATSAPP_TEMPLATE": "axia_plan"}):
            payload = whatsapp._cloud_payload("34612345678", "hi", ["Maria", "WhatsApp Automation", "https://x"])
        self.assertEqual(payload["template"]["name"], "axia_plan")
        self.assertEqual(len(payload["template"]["components"][0]["parameters"]), 3)

    def test_sends_with_credentials(self):
        env = {"WHATSAPP_TOKEN": "t", "WHATSAPP_PHONE_NUMBER_ID": "1"}
        with mock.patch.dict(os.environ, env), mock.patch.object(whatsapp, "_post", return_value={"messages": [{"id": "wamid.1"}]}) as post:
            p = core.build(FORM, "https://site.example", "https://site.example")
        self.assertTrue(p["whatsapp"]["sent"])
        self.assertEqual(post.call_count, 2)  # visitor + owner alert
        self.assertEqual(post.call_args_list[0].args[0]["to"], "34612345678")


class DeckTest(unittest.TestCase):
    def test_renders_and_escapes(self):
        p = core.build({**FORM, "business_name": "<script>x</script>"}, "https://s", "https://s")
        out = deck.render(p)
        self.assertEqual(out.count('class="slide'), 8)
        self.assertNotIn("<script>x", out)


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, path, body=None):
        r = urllib.request.Request(self.base + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_flow(self):
        server._hits.clear()
        status, body = self.req("/api/proposals", FORM)
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertNotIn("whatsapp", created["intake"])
        self.assertIn("save_link", created["whatsapp"])

        status, body = self.req(f"/api/proposals/{created['id']}")
        public = json.loads(body)
        self.assertEqual(status, 200)
        self.assertNotIn("save_link", public["whatsapp"])
        self.assertNotIn("34612345678", body.decode())

        status, body = self.req(f"/p/{created['id']}/deck")
        self.assertEqual(status, 200)
        self.assertIn(b"Casa Verde Furniture", body)

        self.assertEqual(self.req("/api/proposals/nope")[0], 404)
        self.assertEqual(self.req("/api/proposals", {**FORM, "service": "x"})[0], 400)
        self.assertEqual(self.req("/health")[0], 200)

    def test_rate_limit(self):
        server._hits.clear()
        codes = [self.req("/api/proposals", FORM)[0] for _ in range(server.RATE_LIMIT + 1)]
        self.assertEqual(codes[-1], 429)
        server._hits.clear()


if __name__ == "__main__":
    unittest.main()
