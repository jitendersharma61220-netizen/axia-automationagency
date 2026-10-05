"""Decides which messages are due and sends them."""

from datetime import timedelta

from . import templates
from .store import now


def due_steps(lead, sent, followup_days, at):
    """Steps that are due for this lead and not yet sent."""
    if lead.replied:
        return []
    return [
        step
        for step, days in enumerate(followup_days)
        if step not in sent and at >= lead.created_at + timedelta(days=days)
    ]


def send_step(store, mailer, settings, lead, step):
    rendered = templates.render(step, lead, settings.business_name)
    if rendered is None:
        return False
    subject, body = rendered
    mailer.send(lead.email, subject, body)
    store.record_sent(lead.id, step)
    return True


def notify_owner(mailer, settings, lead):
    """Tell the business owner a new lead came in."""
    if not settings.owner_email:
        return
    body = (
        f"New lead for {settings.business_name}\n\n"
        f"Name: {lead.name}\nEmail: {lead.email}\nPhone: {lead.phone}\n"
        f"Source: {lead.source}\n\nMessage:\n{lead.message}\n"
    )
    mailer.send(settings.owner_email, f"New lead: {lead.name}", body)


def handle_new_lead(store, mailer, settings, **fields):
    """Save a lead, alert the owner, and send the instant reply if it is new."""
    existing = store.get_by_email(fields.get("email", ""))
    lead = store.add_lead(**fields)
    if existing is None:
        notify_owner(mailer, settings, lead)
        run_due(store, mailer, settings, leads=[lead])
    return lead


def run_due(store, mailer, settings, at=None, leads=None):
    """Send every due follow-up. Safe to run repeatedly (e.g. from cron)."""
    at = at or now()
    count = 0
    for lead in leads if leads is not None else store.open_leads():
        # Only the most recent due step is sent, so a lead never gets a burst
        # of catch-up messages if the job was down for a few days.
        steps = due_steps(lead, store.sent_steps(lead.id), settings.followup_days, at)
        if steps:
            latest = steps[-1]
            for skipped in steps[:-1]:
                store.record_sent(lead.id, skipped, at)
            if send_step(store, mailer, settings, lead, latest):
                count += 1
    return count
