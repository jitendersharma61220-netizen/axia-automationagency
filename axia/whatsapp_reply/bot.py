"""Answers customer questions from the business's FAQ.

With AI: Claude reads the whole FAQ and answers in the customer's own language
(Hindi, Hinglish or English), and says when it is not sure. Without AI: the
closest FAQ entry by shared keywords is returned.
Either way, anything the FAQ does not cover is handed to a human.
"""

import re
from dataclasses import dataclass

HANDOFF = "Thanks for your message! Our team will reply to you personally very soon."

STOPWORDS = set("""
a an the is are was were be do does did i you we it this that to of in on for
at by with and or what when where how which who can could will would my your
me please hi hello sir madam ji
kya hai hain ka ki ke ko se me mein aap ap hum mujhe kitna kitni kitne kab kaha
kahan kaise kaun bhi tha thi ho hota hoti batao bataye bataiye kar karo krna
""".split())


@dataclass
class FaqEntry:
    question: str
    answer: str


@dataclass
class Reply:
    text: str
    handoff: bool  # True when a human should follow up


def load_faq(path):
    """Read a FAQ file made of "Q: ..." / "A: ..." pairs."""
    with open(path, encoding="utf-8") as f:
        return parse_faq(f.read())


def parse_faq(text):
    entries = []
    for block in re.split(r"\n\s*(?=Q:)", text.strip()):
        m = re.match(r"Q:\s*(.+?)\s*\nA:\s*(.+)", block.strip(), re.S)
        if m:
            entries.append(FaqEntry(m.group(1).strip(), " ".join(m.group(2).split())))
    return entries


def keywords(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    # Crude plural folding so "timing" matches "timings".
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words if w not in STOPWORDS}


def match_faq(faq, message):
    """Best FAQ entry by keyword overlap, or None if nothing is close enough."""
    words = keywords(message)
    best, best_score = None, 0.0
    for entry in faq:
        q = keywords(entry.question)
        if not q or not words:
            continue
        score = len(words & q) / min(len(q), len(words))
        if score > best_score:
            best, best_score = entry, score
    return best if best_score >= 0.5 else None


ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "covered_by_faq": {"type": "boolean"},
    },
    "required": ["answer", "covered_by_faq"],
    "additionalProperties": False,
}


def answer(faq, message, business, ai=None):
    """Reply to one customer message."""
    if ai is not None:
        from axia.ai import AIError

        faq_text = "\n\n".join(f"Q: {e.question}\nA: {e.answer}" for e in faq)
        system = (
            f"You reply to customer WhatsApp messages for {business}, a local business "
            "in India. Answer only from the FAQ below; never invent prices, timings or "
            "promises. Reply in the same language and script the customer used "
            "(Hindi, Hinglish or English), in 1-3 short friendly sentences. If the FAQ "
            "does not answer the question, set covered_by_faq to false and write a "
            "polite line saying the team will reply personally.\n\nFAQ:\n" + faq_text
        )
        try:
            data = ai.ask_json(system, message, ANSWER_SCHEMA)
            return Reply(data["answer"], handoff=not data["covered_by_faq"])
        except AIError as e:
            print(f"AI unavailable, using FAQ matching: {e}")
    entry = match_faq(faq, message)
    if entry is None:
        return Reply(HANDOFF, handoff=True)
    return Reply(entry.answer, handoff=False)
