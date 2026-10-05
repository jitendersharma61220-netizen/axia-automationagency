"""Classifies a review and drafts a reply.

With AI: Claude reads the review, finds what the customer liked or disliked,
and writes a specific reply in the reviewer's language. Without AI: the star
rating and a few keywords pick a polite template.
"""

import re
from dataclasses import dataclass

NEGATIVE_WORDS = re.compile(
    r"\b(rude|worst|bad|dirty|late|delay|waited|waiting|overcharg\w*|refund|cheat\w*|"
    r"pain|never again|disappoint\w*|unprofessional|bekar|ghatiya|bakwas)\b", re.I)


@dataclass
class Review:
    reviewer: str
    rating: int
    text: str


@dataclass
class Result:
    sentiment: str  # positive, neutral or negative
    alert_owner: bool
    reply: str


SCHEMA = {
    "type": "object",
    "properties": {
        "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
        "alert_owner": {
            "type": "boolean",
            "description": "true if an unhappy customer should get a personal call",
        },
        "reply": {"type": "string"},
    },
    "required": ["sentiment", "alert_owner", "reply"],
    "additionalProperties": False,
}


def classify_with_rules(review):
    if review.rating <= 2 or (review.rating == 3 and NEGATIVE_WORDS.search(review.text)):
        return "negative"
    if review.rating == 3 or NEGATIVE_WORDS.search(review.text):
        return "neutral"
    return "positive"


def template_reply(review, sentiment, business, phone=""):
    name = review.reviewer.split()[0] if review.reviewer.strip() else "there"
    if sentiment == "positive":
        return (f"Thank you so much, {name}! We're glad you had a great experience at "
                f"{business}. See you again soon!")
    if sentiment == "neutral":
        return (f"Thank you for your feedback, {name}. We're always working to improve, "
                f"and we hope to make your next visit to {business} even better.")
    contact = f" on {phone}" if phone else ""
    return (f"Hi {name}, we're really sorry about your experience. This is not the "
            f"standard we aim for at {business}. Please contact us{contact} so we can "
            "make it right.")


def handle(review, business, ai=None, phone=""):
    if ai is not None:
        from axia.ai import AIError

        contact = f" Invite unhappy customers to call {phone}." if phone else ""
        system = (
            f"You write replies to Google reviews for {business}, a local business in "
            "India. Classify the review, then write a warm 2-3 sentence reply that "
            "mentions what the customer actually said. Reply in the reviewer's language "
            "(Hindi, Hinglish or English). Never admit legal fault, offer money, or "
            "share private details; for complaints apologise and invite them to talk "
            f"directly.{contact}"
        )
        prompt = f"Reviewer: {review.reviewer}\nRating: {review.rating}/5\nReview: {review.text}"
        try:
            data = ai.ask_json(system, prompt, SCHEMA)
            return Result(data["sentiment"], data["alert_owner"], data["reply"])
        except AIError as e:
            print(f"AI unavailable, using templates: {e}")
    sentiment = classify_with_rules(review)
    return Result(sentiment, sentiment == "negative",
                  template_reply(review, sentiment, business, phone))
