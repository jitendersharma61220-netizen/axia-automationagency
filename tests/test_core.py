import unittest
from types import SimpleNamespace

from axia.core.ai import AIError, ClaudeAI
from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import DryRun


def block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeClient:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


class ClaudeAITest(unittest.TestCase):
    def test_ask_json_parses_structured_output(self):
        client = FakeClient(SimpleNamespace(
            stop_reason="end_turn", content=[block("text", text='{"score": 70}')]))
        out = ClaudeAI(client).ask_json("t", "sys", "hi", {"type": "object"})
        self.assertEqual(out, {"score": 70})
        req = client.requests[0]
        self.assertEqual(req["model"], "claude-opus-5-5")
        self.assertEqual(req["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(req["fallbacks"], "default")

    def test_refusal_raises(self):
        client = FakeClient(SimpleNamespace(stop_reason="refusal", content=[]))
        with self.assertRaises(AIError):
            ClaudeAI(client).ask_json("t", "sys", "hi", {})

    def test_research_resumes_paused_turn(self):
        paused = SimpleNamespace(stop_reason="pause_turn", content=[block("text", text="...")])
        done = SimpleNamespace(stop_reason="end_turn", content=[block("text", text="- fact")])
        client = FakeClient(paused, done)
        self.assertEqual(ClaudeAI(client).research("t", "sys", "find"), "- fact")
        self.assertEqual(client.requests[1]["messages"][1]["role"], "assistant")
        self.assertEqual(client.requests[0]["tools"][0]["name"], "web_search")


class ApprovalsTest(unittest.TestCase):
    def setUp(self):
        self.channels = DryRun(out=lambda _: None)
        self.approvals = Approvals(connect(":memory:"), "sales")

    def test_review_mode_waits_for_approval(self):
        outbox = Outbox(self.approvals, self.channels)
        item = outbox.send("email", "a@b.co", "Hello", subject="Hi")
        self.assertEqual(self.channels.sent, [])
        self.approvals.approve(item, {"body": "Hello (edited)"})
        self.assertEqual(self.channels.sent[0]["body"], "Hello (edited)")
        self.assertEqual(self.approvals.pending(), [])
        with self.assertRaises(ValueError):
            self.approvals.approve(item)

    def test_auto_send_but_sensitive_messages_still_reviewed(self):
        outbox = Outbox(self.approvals, self.channels, auto_send=True)
        outbox.send("whatsapp", "919800000000", "Hi")
        outbox.send("whatsapp", "919800000000", "Price question", always_review=True)
        self.assertEqual(len(self.channels.sent), 1)
        self.assertEqual(len(self.approvals.pending()), 1)

    def test_reject(self):
        item = Outbox(self.approvals, self.channels).send("email", "a@b.co", "x")
        self.approvals.reject(item)
        self.assertEqual(self.channels.sent, [])
        self.assertEqual(self.approvals.get(item)["status"], "rejected")
