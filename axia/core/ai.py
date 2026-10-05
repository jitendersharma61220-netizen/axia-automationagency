"""Shared Claude client used by every agent.

Agents call Claude for one well-defined step at a time (research, score,
draft, classify) and get structured JSON back, so the code around them stays
in control of what actually gets sent, saved or booked.

Needs `pip install anthropic` and an ANTHROPIC_API_KEY.
"""

import base64
import json
import os

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}


class AIError(Exception):
    """Claude could not give a usable answer for this step."""


class ClaudeAI:
    def __init__(self, client=None, model=MODEL, log=None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.log = log or (lambda msg: None)

    def _create(self, **kwargs):
        try:
            return self.client.beta.messages.create(
                model=self.model,
                # If a safety check declines a request, the API retries it on
                # Anthropic's recommended fallback model.
                betas=[FALLBACK_BETA],
                fallbacks="default",
                **kwargs,
            )
        except Exception as e:  # network, auth, rate limit
            raise AIError(f"Claude request failed: {e}") from e

    def ask_json(self, task, system, content, schema, effort="medium", max_tokens=16000):
        """One step that returns a dict matching `schema` (a JSON schema).

        `task` names the step for logs. `content` is a string or a list of
        content blocks (text, images).
        """
        self.log(f"AI step: {task}")
        response = self._create(
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort,
                           "format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason in ("refusal", "max_tokens"):
            raise AIError(f"{task}: Claude stopped early ({response.stop_reason})")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise AIError(f"{task}: Claude returned invalid JSON") from e

    def research(self, task, system, prompt, effort="medium", max_tokens=16000):
        """A step where Claude searches the web and writes up what it found."""
        self.log(f"AI research: {task}")
        messages = [{"role": "user", "content": prompt}]
        for _ in range(5):
            response = self._create(
                max_tokens=max_tokens, system=system, messages=messages,
                tools=[WEB_SEARCH], output_config={"effort": effort},
            )
            if response.stop_reason != "pause_turn":
                break
            # A long search turn paused; send it back so Claude continues it.
            messages = [messages[0], {"role": "assistant", "content": response.content}]
        if response.stop_reason in ("refusal", "pause_turn"):
            raise AIError(f"{task}: research did not finish ({response.stop_reason})")
        return "\n".join(b.text for b in response.content if b.type == "text").strip()


def image_block(path):
    """Content block for a photo or scan (e.g. a bill sent on WhatsApp)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
             "webp": "image/webp", "gif": "image/gif"}.get(ext)
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    if ext == "pdf":
        return {"type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": data}}
    if media is None:
        raise ValueError(f"unsupported file type: {path}")
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def make_ai(log=print):
    """The Claude client. Credentials come from ANTHROPIC_API_KEY (see .env.example)."""
    try:
        return ClaudeAI(log=log)
    except ImportError:
        raise SystemExit("Install the Claude SDK first: pip install anthropic")
