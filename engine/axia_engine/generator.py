"""Write the tailored part of a proposal: the concept in the visitor's terms,
a demo set in their business, the rollout plan and the WhatsApp wording.

Uses the Claude API when ANTHROPIC_API_KEY (or another Anthropic credential)
is configured; otherwise falls back to a template writer so the engine still
works end to end in a demo or a test.
"""

import json
import logging
import os
import re

from .services import SERVICES

log = logging.getLogger(__name__)

MODEL = os.environ.get("AXIA_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("AXIA_EFFORT", "medium")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["headline", "problem_summary", "why_you_need_it", "how_it_works", "demo", "rollout", "whatsapp_problem", "whatsapp_solution"],
    "properties": {
        "headline": {"type": "string", "description": "One line promise for this business, under 12 words."},
        "problem_summary": {"type": "string", "description": "Their problem restated in 2 to 3 plain sentences, so they feel understood."},
        "why_you_need_it": {"type": "array", "items": {"type": "string"}, "description": "3 to 5 reasons this service fits their business, each tied to something they told us."},
        "how_it_works": {
            "type": "array",
            "description": "One item per engine stage, in order, explained for this business.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["step", "detail"],
                "properties": {"step": {"type": "string"}, "detail": {"type": "string"}},
            },
        },
        "demo": {
            "type": "object",
            "additionalProperties": False,
            "required": ["scenario", "messages", "behind_the_scenes"],
            "properties": {
                "scenario": {"type": "string", "description": "One sentence setting the scene in their business."},
                "messages": {
                    "type": "array",
                    "description": "6 to 10 short messages showing their exact problem being solved.",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["sender", "text"],
                        "properties": {
                            "sender": {"type": "string", "enum": ["customer", "engine", "team"]},
                            "text": {"type": "string"},
                        },
                    },
                },
                "behind_the_scenes": {"type": "array", "items": {"type": "string"}, "description": "3 to 5 things the engine did silently during the demo (updated a sheet, alerted a person, scheduled a follow-up)."},
            },
        },
        "rollout": {
            "type": "array",
            "description": "3 to 4 phases from kickoff to fully live.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["when", "what"],
                "properties": {"when": {"type": "string"}, "what": {"type": "string"}},
            },
        },
        "whatsapp_problem": {"type": "string", "description": "1 to 2 sentences for a WhatsApp message: the problem as we understood it."},
        "whatsapp_solution": {"type": "string", "description": "1 to 2 sentences for a WhatsApp message: what the engine will do about it."},
    },
}

SYSTEM = """You write tailored proposals for AXIA, an automation agency that builds department automation engines for businesses in any country.

A visitor has picked a service on the AXIA website and described their business. Write the parts of their proposal that must be tailored to them, so that they see their own problem being solved.

Rules:
- Never use the words "AI", "A.I." or "artificial intelligence". Say "the engine", "automation" or describe what it does.
- Be concrete and specific to their industry, customers and problem. No generic filler.
- The demo must show their exact problem being solved, with realistic names, products and amounts for their kind of business and country. Customer messages may be in the language their customers would use.
- Important decisions always go to a person on their team; show that where it fits.
- Do not quote any savings, revenue or profit numbers. Those are calculated separately.
- Plain, warm, confident language. Short sentences.
- Write everything in the language requested."""


def _brand_safe(value):
    """Remove the word AI from generated text (public brand rule)."""
    if isinstance(value, str):
        value = re.sub(r"\bartificial intelligence\b", "automation", value, flags=re.I)
        value = re.sub(r"\bA\.?I\.?[- ](powered|driven|based)\b", "automated", value)
        value = re.sub(r"\b(AI|A\.I\.)(?!\w)", "automation", value)
        return value
    if isinstance(value, list):
        return [_brand_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _brand_safe(v) for k, v in value.items()}
    return value


def _brief(intake, numbers):
    svc = SERVICES[intake["service"]]
    return json.dumps(
        {
            "service": {"name": svc["name"], "what_it_does": svc["concept"], "stages": svc["stages"], "connects_to": svc["tools"]},
            "visitor": {
                "name": intake["name"],
                "business_name": intake["business_name"],
                "industry": intake["industry"],
                "country": intake["country"],
                "what_the_business_does": intake["business_description"],
                "main_problem": intake["main_problem"],
                "team_size": intake["team_size"],
                "customer_enquiries_per_month": intake["monthly_inquiries"],
                "hours_per_week_on_this_work": intake["hours_per_week"],
            },
            "write_in_language": intake["language"],
            "estimated_hours_saved_per_month": numbers["hours_saved_month"],
        },
        ensure_ascii=False,
        indent=2,
    )


def _with_claude(intake, numbers):
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": "Write the tailored proposal content for this visitor.\n\n" + _brief(intake, numbers)}],
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"generation stopped: {response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def _with_template(intake, numbers):
    """Deterministic fallback used when no Anthropic credential is configured."""
    svc = SERVICES[intake["service"]]
    biz = intake["business_name"]
    industry = intake["industry"] or "your industry"
    problem = intake["main_problem"].rstrip(".")
    demos = {
        "whatsapp": [
            ("customer", f"Hi, is this {biz}? What are your prices and are you open today?"),
            ("engine", f"Hi! Yes, this is {biz}. We are open until 8 pm today. Here is our price list. Which one are you interested in?"),
            ("customer", "The second one. Can I book for tomorrow?"),
            ("engine", "Of course. Tomorrow we have 11:00, 2:30 and 5:00 free. Which suits you?"),
            ("customer", "2:30 please"),
            ("engine", "Booked for tomorrow at 2:30. You will get a reminder an hour before. Here is your payment link to confirm."),
            ("team", "New confirmed booking for tomorrow 2:30, paid in advance."),
        ],
        "sales": [
            ("engine", f"New lead found and researched. Fit score 86/100. Draft message ready for approval."),
            ("team", "Approved, send it."),
            ("customer", "Thanks for reaching out. Can you share pricing?"),
            ("engine", "Happy to. Here is a short overview. Would Thursday 11:00 or Friday 3:00 work for a 20 minute call?"),
            ("customer", "Friday works."),
            ("engine", "Booked for Friday 3:00. Invite sent and your CRM is updated."),
        ],
        "marketing": [
            ("team", "Goal for next month: 20% more enquiries for our best seller."),
            ("engine", "Plan ready: 12 posts, 2 emails and 1 WhatsApp broadcast. Drafts are waiting for your approval."),
            ("team", "Approved, but change the offer to free delivery."),
            ("engine", "Updated and scheduled. First post goes live Monday 10:00."),
            ("engine", "Week 1 report: the reel brought 3x more enquiries than the carousel. Shifting budget to reels."),
        ],
        "accounts": [
            ("engine", "12 new bills arrived today on email and WhatsApp. All read and entered."),
            ("engine", "Bill 4471 does not match purchase order PO-208: 50 units billed, 45 delivered. Held for review."),
            ("team", "Hold it and ask the supplier for a corrected bill."),
            ("engine", "Done. The supplier has been asked for a corrected bill. 11 bills are ready for payment approval."),
            ("team", "Approve all 11."),
            ("engine", "Payments queued and posted to your books."),
        ],
        "clinic": [
            ("customer", "Hello, I need an appointment with the doctor this week."),
            ("engine", "Hello! The doctor has Wednesday 10:30 or Thursday 5:00 free. Which suits you?"),
            ("customer", "Thursday 5:00"),
            ("engine", "Booked for Thursday at 5:00. We will remind you the day before. Please bring your old reports."),
            ("team", "Visit notes drafted for the doctor to check and sign."),
            ("engine", "Your report has been reviewed by the doctor. Here is a simple explanation of each value."),
        ],
        "hiring": [
            ("engine", "84 applications received for the open role. Top 12 shortlisted with reasons."),
            ("team", "Looks good. Screen the top 12."),
            ("customer", "Hi, yes I am interested. I have 3 years of experience and can join in 30 days."),
            ("engine", "Thank you! Can you do an interview on Tuesday at 11:00 or 4:00?"),
            ("customer", "Tuesday 4:00 works."),
            ("engine", "Interview booked for Tuesday at 4:00 with the hiring manager. Calendar invites sent."),
        ],
    }
    return {
        "headline": f"{svc['name']} built around {biz}",
        "problem_summary": f"You told us: {problem}. That costs {biz} hours every week and customers who never hear back in time.",
        "why_you_need_it": [
            f"Your team spends about {intake['hours_per_week']:g} hours a week on work the engine can do.",
            f"With {intake['monthly_inquiries']:g} enquiries a month, every slow reply is a lost sale.",
            f"It works inside tools you already use: {', '.join(svc['tools'][:3])}.",
            "Your team stays in control: important decisions always come to a person.",
        ],
        "how_it_works": [{"step": s, "detail": f"{s} for {biz}, set up around how {industry} works."} for s in svc["stages"]],
        "demo": {
            "scenario": f"A normal day at {biz}.",
            "messages": [{"sender": a, "text": b} for a, b in demos[intake["service"]]],
            "behind_the_scenes": [
                "Logged every conversation in your sheet or CRM.",
                "Alerted your team only when a person was needed.",
                "Scheduled follow-ups for anyone who went quiet.",
            ],
        },
        "rollout": [
            {"when": "Week 1", "what": "Process audit and setup on your WhatsApp and tools."},
            {"when": "Week 2", "what": "Pilot on real conversations with your team watching."},
            {"when": "Week 3 onwards", "what": "Fully live, with a monthly report of hours saved and results."},
        ],
        "whatsapp_problem": f"{problem}.",
        "whatsapp_solution": f"Our {svc['name']} takes this work over for {biz} and only brings your team in when a decision is needed.",
    }


def generate(intake, numbers):
    """Return (content, source) where source is 'claude' or 'template'."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        try:
            return _brand_safe(_with_claude(intake, numbers)), "claude"
        except Exception:
            log.exception("Claude generation failed, using the template writer")
    return _brand_safe(_with_template(intake, numbers)), "template"
