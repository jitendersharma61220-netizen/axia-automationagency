"""Shared Claude client used by every AI-powered automation.

Each automation works without AI too (simple rules), so a client can start
free and switch on AI later. AI is used when ANTHROPIC_API_KEY is set and the
`anthropic` package is installed (pip install anthropic). Set AXIA_AI=off to
force the rule-based mode.
"""

import base64
import json
import os

MODEL = "claude-opus-5-5"


class AIError(Exception):
    """Claude could not give a usable answer; callers fall back to rules."""


class ClaudeAI:
    def __init__(self, client=None, model=MODEL):
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.model = model

    def ask_json(self, system, content, schema, effort="low", max_tokens=16000):
        """Ask Claude and get back a dict matching `schema` (a JSON schema).

        `content` is a string or a list of content blocks (text, images).
        """
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                # If a safety check declines the request, let the API retry it
                # on Anthropic's recommended fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except Exception as e:  # network, auth, rate limit: use the rule-based path
            raise AIError(f"Claude request failed: {e}") from e
        if response.stop_reason in ("refusal", "max_tokens"):
            raise AIError(f"Claude stopped early: {response.stop_reason}")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise AIError("Claude returned invalid JSON") from e


def image_block(path):
    """Content block for a photo (e.g. a bill sent on WhatsApp)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    media = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
             "webp": "image/webp", "gif": "image/gif"}.get(ext)
    if media is None:
        raise ValueError(f"unsupported image type: {path}")
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}


def make_ai(env=None):
    """Return a ClaudeAI if AI is configured, else None (rule-based mode)."""
    env = os.environ if env is None else env
    if env.get("AXIA_AI", "on") == "off" or not env.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return ClaudeAI()
    except ImportError:
        print("anthropic package not installed; using rule-based mode (pip install anthropic)")
        return None


def business_name(env=None):
    env = os.environ if env is None else env
    return env.get("AXIA_BUSINESS_NAME", "Our Business")
