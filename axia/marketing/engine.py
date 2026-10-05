"""The AI marketing campaign engine: research, plan, create, check, analyse.

1. Research: Claude searches the web for competitors' current offers and
   local events or festivals in the campaign window.
2. Plan: a campaign plan with segments, offer, channel mix and a dated
   content calendar.
3. Create: content for every calendar slot, written to each channel's rules.
   Code checks hard limits (Google Ads lengths, banned phrases) and sends a
   piece back to Claude once if it breaks them.
4. Approve: every piece waits for the owner in the approval queue.
5. Analyse: code computes CTR, cost per lead and ROAS per channel from the
   ad platforms' numbers; Claude explains them and proposes a new budget
   split, which code keeps within safe limits.
"""

import csv
import json
from datetime import date, timedelta

from axia.core.ai import AIError
from axia.core.approvals import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY,
    goal TEXT NOT NULL,
    start TEXT NOT NULL,
    weeks INTEGER NOT NULL,
    research TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
    day TEXT NOT NULL,
    channel TEXT NOT NULL,
    theme TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
);
"""

CHANNELS = ["instagram", "facebook", "whatsapp", "google_ads"]

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "objective": {"type": "string"},
        "segments": {"type": "array", "items": {"type": "string"}},
        "offer": {"type": "string"},
        "key_message": {"type": "string"},
        "channel_mix": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"channel": {"type": "string", "enum": CHANNELS},
                               "share": {"type": "number", "description": "0-1 of budget"},
                               "why": {"type": "string"}},
                "required": ["channel", "share", "why"],
                "additionalProperties": False,
            },
        },
        "calendar": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"day": {"type": "string", "description": "YYYY-MM-DD"},
                               "channel": {"type": "string", "enum": CHANNELS},
                               "theme": {"type": "string"}},
                "required": ["day", "channel", "theme"],
                "additionalProperties": False,
            },
        },
        "kpis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"metric": {"type": "string"}, "target": {"type": "string"}},
                "required": ["metric", "target"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["objective", "segments", "offer", "key_message", "channel_mix",
                 "calendar", "kpis"],
    "additionalProperties": False,
}

_TEXT = {"type": "string"}
_LIST = {"type": "array", "items": {"type": "string"}}


def _obj(**props):
    return {"type": "object", "properties": props, "required": list(props),
            "additionalProperties": False}


CONTENT_SCHEMAS = {
    "instagram": _obj(caption=_TEXT, hashtags=_LIST, visual_brief=_TEXT),
    "facebook": _obj(post=_TEXT, visual_brief=_TEXT),
    "whatsapp": _obj(message=_TEXT, call_to_action=_TEXT),
    "google_ads": _obj(headlines=_LIST, descriptions=_LIST, keywords=_LIST),
}

CHANNEL_RULES = {
    "instagram": "Caption under 150 words with a hook in the first line; 8-15 hashtags "
                 "mixing local and niche tags; a visual brief a designer can shoot from.",
    "facebook": "Post under 120 words, conversational, one clear call to action.",
    "whatsapp": "Broadcast to people who opted in. Under 600 characters, personal tone, "
                "one call to action, an opt-out line at the end.",
    "google_ads": "Responsive search ad: exactly 5 headlines of at most 30 characters, "
                  "3 descriptions of at most 90 characters, 8-12 local search keywords.",
}

ANALYSIS_SCHEMA = _obj(
    summary=_TEXT,
    working=_LIST,
    not_working=_LIST,
    actions=_LIST,
    new_split={"type": "array", "items": _obj(
        channel={"type": "string", "enum": CHANNELS}, share={"type": "number"})},
)

MAX_SHIFT = 0.2  # budget share a channel may gain or lose in one review


class MarketingEngine:
    def __init__(self, conn, ai, approvals, brand, clock=now):
        self.conn = conn
        self.ai = ai
        self.approvals = approvals
        self.brand = brand
        self.clock = clock
        conn.executescript(SCHEMA)
        approvals.on_approve("content", self._mark("approved"))

    def _system(self, task):
        b = self.brand
        return (
            f"You are the marketing team for {b['business']} ({b['location']}). {b['about']}\n"
            f"Audience: {b['audience']}\nBrand voice: {b['voice']}\n"
            f"Never use these phrases: {', '.join(b.get('do_not_say', []))}.\n"
            "Do not invent prices, discounts or facts about the business that are not given.\n\n"
            f"Your task now: {task}"
        )

    # ----- 1 + 2: research and plan --------------------------------------

    def plan(self, goal, start, weeks=4):
        end = start + timedelta(weeks=weeks)
        research = self.ai.research(
            "marketing.research",
            self._system("Research the market before we plan a campaign."),
            f"Campaign goal: {goal}\nWindow: {start} to {end}\n"
            "Find: what 3-5 nearby competitors are offering right now, festivals or local "
            "events in this window that matter for this audience, and one or two trends "
            "worth using. Short factual bullets with sources; say when unsure.")
        channels = [c for c in self.brand["channels"] if c in CHANNELS]
        plan = self.ai.ask_json(
            "marketing.plan",
            self._system("Plan the campaign."),
            f"Goal: {goal}\nWindow: {start} to {end} ({weeks} weeks)\n"
            f"Monthly budget: Rs {self.brand['monthly_budget']}\nChannels: {channels}\n"
            f"Research:\n{research}\n\nBuild a dated calendar of 2-4 posts per week "
            "across these channels, tied to the research (festivals, competitor gaps).",
            PLAN_SCHEMA, effort="high")
        plan["calendar"] = [c for c in plan["calendar"]
                            if c["channel"] in channels and _in_window(c["day"], start, end)]
        plan["channel_mix"] = _normalize_split(
            {m["channel"]: m["share"] for m in plan["channel_mix"] if m["channel"] in channels})
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO campaigns (goal, start, weeks, research, plan, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (goal, start.isoformat(), weeks, research, json.dumps(plan),
                 self.clock().isoformat()))
        return cur.lastrowid

    def campaign(self, campaign_id):
        r = self.conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        if r is None:
            raise ValueError(f"no campaign #{campaign_id}")
        return dict(r, plan=json.loads(r["plan"]))

    # ----- 3 + 4: create, check, queue for approval ----------------------

    def create_content(self, campaign_id):
        c = self.campaign(campaign_id)
        plan = c["plan"]
        made = 0
        for slot in plan["calendar"]:
            exists = self.conn.execute(
                "SELECT 1 FROM content WHERE campaign_id = ? AND day = ? AND channel = ?"
                " AND theme = ?", (campaign_id, slot["day"], slot["channel"], slot["theme"])
            ).fetchone()
            if exists:
                continue  # safe to re-run after a failure
            try:
                body = self._write(plan, slot)
            except AIError as e:
                print(f"{slot['day']} {slot['channel']}: skipped, re-run to retry ({e})")
                continue
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO content (campaign_id, day, channel, theme, body)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (campaign_id, slot["day"], slot["channel"], slot["theme"], json.dumps(body)))
            self.approvals.request(
                "content", f"{slot['day']} {slot['channel']}: {slot['theme']}",
                {"content_id": cur.lastrowid, **body}, ref=campaign_id)
            made += 1
        return made

    def _write(self, plan, slot):
        channel = slot["channel"]
        prompt = (f"Campaign offer: {plan['offer']}\nKey message: {plan['key_message']}\n"
                  f"Post date: {slot['day']}\nTheme: {slot['theme']}\n"
                  f"Channel rules: {CHANNEL_RULES[channel]}")
        task = self._system(f"Write the {channel} content for one calendar slot.")
        body = self.ai.ask_json("marketing.content", task, prompt, CONTENT_SCHEMAS[channel])
        problems = check_content(channel, body, self.brand.get("do_not_say", []))
        if problems:
            body = self.ai.ask_json(
                "marketing.content", task,
                f"{prompt}\n\nYour previous draft broke these rules, fix them:\n- "
                + "\n- ".join(problems) + f"\n\nPrevious draft: {json.dumps(body)}",
                CONTENT_SCHEMAS[channel])
            problems = check_content(channel, body, self.brand.get("do_not_say", []))
            if problems:
                raise AIError("; ".join(problems))
        return body

    def _mark(self, status):
        def handler(payload):
            with self.conn:
                self.conn.execute("UPDATE content SET status = ?, body = ? WHERE id = ?",
                                  (status, json.dumps({k: v for k, v in payload.items()
                                                       if k != "content_id"}),
                                   payload["content_id"]))
        return handler

    def export(self, campaign_id, path):
        """Approved content as a CSV for Meta Business Suite / scheduling tools."""
        rows = self.conn.execute(
            "SELECT day, channel, theme, body FROM content WHERE campaign_id = ?"
            " AND status = 'approved' ORDER BY day, channel", (campaign_id,)).fetchall()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["date", "channel", "theme", "text", "extra"])
            for r in rows:
                body = json.loads(r["body"])
                text, extra = _flatten(r["channel"], body)
                w.writerow([r["day"], r["channel"], r["theme"], text, extra])
        return len(rows)

    # ----- 5: analyse results --------------------------------------------

    def analyze(self, campaign_id, metrics_path):
        c = self.campaign(campaign_id)
        stats = channel_stats(read_metrics(metrics_path))
        current = c["plan"]["channel_mix"]
        a = self.ai.ask_json(
            "marketing.analyze",
            self._system("Review campaign results and recommend changes."),
            f"Goal: {c['goal']}\nKPI targets: {json.dumps(c['plan']['kpis'])}\n"
            f"Current budget split: {json.dumps(current)}\n"
            f"Results per channel (computed): {json.dumps(stats)}\n\n"
            "Explain in plain words for a busy owner. Recommend a new budget split; "
            f"shift at most {int(MAX_SHIFT * 100)} percentage points per channel.",
            ANALYSIS_SCHEMA, effort="high")
        a["new_split"] = limit_shift(current, {s["channel"]: s["share"] for s in a["new_split"]})
        a["stats"] = stats
        return a


def check_content(channel, body, banned):
    problems = []
    if channel == "google_ads":
        long_h = [h for h in body["headlines"] if len(h) > 30]
        long_d = [d for d in body["descriptions"] if len(d) > 90]
        if long_h:
            problems.append(f"headlines over 30 characters: {long_h}")
        if long_d:
            problems.append(f"descriptions over 90 characters: {long_d}")
        if len(body["headlines"]) < 3:
            problems.append("need at least 3 headlines")
    if channel == "whatsapp" and len(body["message"]) > 700:
        problems.append("WhatsApp message over 700 characters")
    text = json.dumps(body, ensure_ascii=False).lower()
    used = [b for b in banned if b.lower() in text]
    if used:
        problems.append(f"uses banned phrases: {used}")
    return problems


def read_metrics(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def channel_stats(rows):
    totals = {}
    for r in rows:
        t = totals.setdefault(r["channel"], dict.fromkeys(
            ["spend", "impressions", "clicks", "leads", "sales", "revenue"], 0.0))
        for k in t:
            t[k] += float(r.get(k) or 0)
    out = {}
    for ch, t in totals.items():
        out[ch] = {
            **{k: round(v, 2) for k, v in t.items()},
            "ctr_pct": round(100 * t["clicks"] / t["impressions"], 2) if t["impressions"] else None,
            "cost_per_lead": round(t["spend"] / t["leads"], 2) if t["leads"] else None,
            "roas": round(t["revenue"] / t["spend"], 2) if t["spend"] else None,
        }
    return out


def _normalize_split(split):
    split = {k: max(0.0, float(v)) for k, v in split.items()}
    total = sum(split.values())
    if not total:
        return {k: round(1 / len(split), 3) for k in split} if split else {}
    return {k: round(v / total, 3) for k, v in split.items()}


def limit_shift(current, proposed):
    """Keep the AI's budget proposal within MAX_SHIFT per channel and summing to 1."""
    out = {}
    for ch, share in current.items():
        want = proposed.get(ch, share)
        out[ch] = min(share + MAX_SHIFT, max(share - MAX_SHIFT, max(0.0, want)))
    return _normalize_split(out)


def _in_window(day, start, end):
    try:
        return start <= date.fromisoformat(day) <= end
    except ValueError:
        return False


def _flatten(channel, body):
    if channel == "instagram":
        return body["caption"], " ".join(body["hashtags"]) + " | visual: " + body["visual_brief"]
    if channel == "facebook":
        return body["post"], "visual: " + body["visual_brief"]
    if channel == "whatsapp":
        return body["message"], body["call_to_action"]
    return " | ".join(body["headlines"]), " | ".join(body["descriptions"])
