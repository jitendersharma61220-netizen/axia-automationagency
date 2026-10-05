"""Settings read from environment variables (see .env.example)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    business_name: str
    owner_email: str
    db_path: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    dry_run: bool
    # Days after the lead arrives to send each follow-up (day 0 is the instant reply).
    followup_days: tuple

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        days = env.get("AXIA_FOLLOWUP_DAYS", "0,2,5")
        return cls(
            business_name=env.get("AXIA_BUSINESS_NAME", "Our Business"),
            owner_email=env.get("AXIA_OWNER_EMAIL", ""),
            db_path=env.get("AXIA_DB_PATH", "leads.db"),
            smtp_host=env.get("AXIA_SMTP_HOST", ""),
            smtp_port=int(env.get("AXIA_SMTP_PORT", "587")),
            smtp_user=env.get("AXIA_SMTP_USER", ""),
            smtp_password=env.get("AXIA_SMTP_PASSWORD", ""),
            from_email=env.get("AXIA_FROM_EMAIL", ""),
            dry_run=env.get("AXIA_DRY_RUN", "1") != "0",
            followup_days=tuple(int(d) for d in days.split(",") if d.strip()),
        )
