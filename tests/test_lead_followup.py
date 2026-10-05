import json
import threading
import unittest
import urllib.request
from datetime import timedelta
from http.server import ThreadingHTTPServer

from axia.lead_followup import engine, webhook
from axia.lead_followup.config import Settings
from axia.lead_followup.mailer import DryRunMailer
from axia.lead_followup.store import Store, now


def settings(**over):
    env = {"AXIA_BUSINESS_NAME": "Smile Dental", "AXIA_DB_PATH": ":memory:"}
    env.update(over)
    return Settings.from_env(env)


class LeadFollowupTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.mailer = DryRunMailer(out=lambda _: None)
        self.settings = settings(AXIA_OWNER_EMAIL="owner@smile.test")

    def test_new_lead_gets_instant_reply_and_owner_alert(self):
        engine.handle_new_lead(self.store, self.mailer, self.settings,
                               name="Asha Rao", email="Asha@Example.com")
        recipients = [m[0] for m in self.mailer.sent]
        self.assertEqual(recipients, ["owner@smile.test", "asha@example.com"])
        self.assertIn("Hi Asha", self.mailer.sent[1][2])
        self.assertIn("Smile Dental", self.mailer.sent[1][1])

    def test_duplicate_lead_is_not_messaged_twice(self):
        for _ in range(2):
            engine.handle_new_lead(self.store, self.mailer, self.settings,
                                   name="Asha", email="asha@example.com")
        self.assertEqual(len(self.mailer.sent), 2)  # owner alert + one reply

    def test_invalid_email_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add_lead("Asha", "not-an-email")

    def test_followups_sent_on_schedule(self):
        start = now() - timedelta(days=10)
        lead = self.store.add_lead("Ravi", "ravi@example.com", created_at=start)
        s = settings()
        self.assertEqual(engine.run_due(self.store, self.mailer, s, at=start), 1)
        self.assertEqual(engine.run_due(self.store, self.mailer, s, at=start + timedelta(days=1)), 0)
        self.assertEqual(engine.run_due(self.store, self.mailer, s, at=start + timedelta(days=2)), 1)
        self.assertEqual(engine.run_due(self.store, self.mailer, s, at=start + timedelta(days=5)), 1)
        self.assertEqual(engine.run_due(self.store, self.mailer, s, at=start + timedelta(days=9)), 0)
        self.assertEqual(self.store.sent_steps(lead.id), {0, 1, 2})

    def test_catch_up_sends_only_latest_step(self):
        start = now() - timedelta(days=10)
        lead = self.store.add_lead("Ravi", "ravi@example.com", created_at=start)
        self.assertEqual(engine.run_due(self.store, self.mailer, settings()), 1)
        self.assertEqual(self.mailer.sent[0][1], "Still interested?")
        self.assertEqual(self.store.sent_steps(lead.id), {0, 1, 2})

    def test_replied_lead_gets_no_more_messages(self):
        start = now() - timedelta(days=3)
        self.store.add_lead("Ravi", "ravi@example.com", created_at=start)
        self.store.mark_replied("RAVI@example.com")
        self.assertEqual(engine.run_due(self.store, self.mailer, settings()), 0)


class WebhookTest(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.mailer = DryRunMailer(out=lambda _: None)
        handler = webhook.make_handler(self.store, self.mailer, settings())
        handler.log_message = lambda *a: None
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def post(self, data, content_type="application/json"):
        body = json.dumps(data).encode() if "json" in content_type else data.encode()
        req = urllib.request.Request(self.url + "/lead", data=body,
                                     headers={"Content-Type": content_type})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_json_lead(self):
        status, _ = self.post({"name": "Meera", "email": "meera@example.com"})
        self.assertEqual(status, 201)
        self.assertEqual(self.mailer.sent[0][0], "meera@example.com")

    def test_form_lead(self):
        status, _ = self.post("name=Meera&email=meera%40example.com",
                              "application/x-www-form-urlencoded")
        self.assertEqual(status, 201)

    def test_missing_email_is_400(self):
        status, payload = self.post({"name": "Meera"})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
