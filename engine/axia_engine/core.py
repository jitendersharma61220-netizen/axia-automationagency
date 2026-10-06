"""Build, store and load proposals."""

import json
import os
import re
import secrets
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from . import generator, roi, whatsapp
from .intake import parse
from .services import SERVICES

DATA_DIR = Path(os.environ.get("AXIA_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
_lock = threading.Lock()
_ID = re.compile(r"^[A-Za-z0-9_-]{8,32}$")


def _path(pid):
    return DATA_DIR / "proposals" / f"{pid}.json"


def build(form, site_url, api_url):
    """Run the whole engine for one visitor. Raises intake.IntakeError on bad input."""
    intake = parse(form)
    svc = SERVICES[intake["service"]]
    numbers = roi.estimate(intake)
    content, source = generator.generate(intake, numbers)

    pid = secrets.token_urlsafe(9)
    proposal_url = f"{site_url.rstrip('/')}/plan.html?id={pid}"
    if site_url.rstrip("/") != api_url.rstrip("/"):
        proposal_url += "&engine=" + urllib.parse.quote(api_url.rstrip("/"), safe="")
    text = whatsapp.compose(intake, content, numbers, svc["name"], proposal_url)
    delivery = whatsapp.deliver(intake, text, svc["name"], proposal_url)

    proposal = {
        "id": pid,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "service": intake["service"],
        "service_name": svc["name"],
        "stages": svc["stages"],
        "tools": svc["tools"],
        "concept": svc["concept"],
        "intake": intake,
        "numbers": numbers,
        "content": content,
        "source": source,
        "proposal_url": proposal_url,
        "deck_url": f"{api_url.rstrip('/')}/p/{pid}/deck",
        "whatsapp": delivery,
    }
    with _lock:
        (DATA_DIR / "proposals").mkdir(parents=True, exist_ok=True)
        _path(pid).write_text(json.dumps(proposal, ensure_ascii=False, indent=2))
        with open(DATA_DIR / "leads.jsonl", "a") as f:
            f.write(json.dumps({
                "id": pid, "created": proposal["created"], "service": intake["service"],
                "name": intake["name"], "business": intake["business_name"], "country": intake["country"],
                "whatsapp": intake["whatsapp"], "whatsapp_sent": delivery["sent"], "source": source,
            }, ensure_ascii=False) + "\n")
    return proposal


def load(pid):
    if not _ID.match(pid or ""):
        return None
    try:
        return json.loads(_path(pid).read_text())
    except FileNotFoundError:
        return None


def public_view(proposal, creator=False):
    """What anyone holding the link may see: no phone number, no internal fields.

    The visitor who just filled the form also gets the link that saves the
    message to their own WhatsApp.
    """
    p = json.loads(json.dumps(proposal))
    p["intake"].pop("whatsapp", None)
    if not creator:
        p["whatsapp"].pop("save_link", None)
    p["whatsapp"].pop("error", None)
    p["whatsapp"].pop("message_id", None)
    return p
