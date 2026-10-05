"""Message templates for each step of the follow-up sequence.

Edit these per client. Placeholders: $first_name, $business.
"""

from string import Template

STEPS = [
    (
        "Thanks for reaching out to $business",
        "Hi $first_name,\n\n"
        "Thanks for getting in touch with $business. We've received your message "
        "and someone from our team will contact you shortly.\n\n"
        "If it's urgent, just reply to this email.\n\n"
        "Best,\n$business",
    ),
    (
        "Quick check-in from $business",
        "Hi $first_name,\n\n"
        "Just following up on your enquiry. Would you like to book a quick call "
        "this week? Reply with a time that suits you.\n\n"
        "Best,\n$business",
    ),
    (
        "Still interested?",
        "Hi $first_name,\n\n"
        "We don't want you to miss out. If you're still interested, reply to this "
        "email and we'll take it from there. If not, no worries, we won't keep "
        "messaging you.\n\n"
        "Best,\n$business",
    ),
]


def render(step, lead, business):
    """Return (subject, body) for a step, or None if the step has no template."""
    if step >= len(STEPS):
        return None
    subject, body = STEPS[step]
    values = {"first_name": lead.name.split()[0], "business": business}
    return Template(subject).safe_substitute(values), Template(body).safe_substitute(values)
