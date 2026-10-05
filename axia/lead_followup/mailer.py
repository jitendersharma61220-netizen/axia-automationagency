"""Email senders: a real SMTP sender and a dry-run sender for testing."""

import smtplib
from email.message import EmailMessage


class DryRunMailer:
    """Prints messages instead of sending them. Keeps a list for tests."""

    def __init__(self, out=print):
        self.sent = []
        self.out = out

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))
        self.out(f"[dry-run] to={to} subject={subject!r}")


class SmtpMailer:
    def __init__(self, settings):
        self.s = settings

    def send(self, to, subject, body):
        msg = EmailMessage()
        msg["From"] = self.s.from_email
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password)
            smtp.send_message(msg)


def make_mailer(settings):
    return DryRunMailer() if settings.dry_run else SmtpMailer(settings)
