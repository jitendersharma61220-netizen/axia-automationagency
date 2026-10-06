"""Send the proposal summary on WhatsApp.

With WhatsApp Cloud API credentials the message is sent directly from the
AXIA business number. Without them nothing is sent: the engine returns
click-to-chat links instead (one for the visitor to save the message to their
own WhatsApp, one for the AXIA team to send it by hand).

WhatsApp only lets a business start a conversation with an approved message
template. Set WHATSAPP_TEMPLATE to the template's name to use it; its body
must take three parameters: {{1}} visitor name, {{2}} service name,
{{3}} proposal link. Without a template the engine sends free text, which
WhatsApp only delivers inside a 24 hour window after the visitor last wrote
to the business (fine for test numbers).
"""

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v21.0")
OWNER_NUMBER = os.environ.get("AXIA_OWNER_WHATSAPP", "918930522312")


def compose(intake, content, numbers, service_name, proposal_url):
    d = numbers["display"]
    lines = [
        f"Hi {intake['name']}, this is AXIA. Here is your {service_name} plan for {intake['business_name']}.",
        "",
        "*Your problem*",
        content["whatsapp_problem"],
        "",
        "*The solution*",
        content["whatsapp_solution"],
        "",
        "*What it is worth (estimate)*",
        f"Time saved: {d['hours_saved_month']} a month ({d['labour_saving_month']})",
    ]
    if numbers["extra_profit_month"]:
        lines.append(f"Extra profit from faster replies: {d['extra_profit_month']} a month")
    lines += [
        f"Total gain: {d['monthly_gain']} a month, about {d['yearly_gain']} a year",
        "",
        f"Your demo and deck: {proposal_url}",
        "",
        "Reply here to book a free process audit.",
    ]
    return "\n".join(lines)


def wa_link(number, text):
    return f"https://wa.me/{number}?text={urllib.parse.quote(text)}"


def _post(payload):
    token = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    req = urllib.request.Request(
        f"https://graph.facebook.com/{GRAPH_VERSION}/{phone_id}/messages",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def _cloud_payload(to, text, template_params):
    template = os.environ.get("WHATSAPP_TEMPLATE")
    if template:
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template,
                "language": {"code": os.environ.get("WHATSAPP_TEMPLATE_LANG", "en")},
                "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in template_params]}],
            },
        }
    return {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"preview_url": True, "body": text}}


def configured():
    return bool(os.environ.get("WHATSAPP_TOKEN") and os.environ.get("WHATSAPP_PHONE_NUMBER_ID"))


def deliver(intake, text, service_name, proposal_url):
    """Send to the visitor and alert the AXIA owner. Never raises."""
    result = {
        "text": text,
        "save_link": wa_link(intake["whatsapp"], text),
        "chat_link": wa_link(OWNER_NUMBER, f"Hi AXIA, I just got my {service_name} plan. I would like a free process audit."),
        "sent": False,
        "mode": "link",
    }
    if not configured():
        return result
    try:
        resp = _post(_cloud_payload(intake["whatsapp"], text, [intake["name"], service_name, proposal_url]))
        result.update(sent=True, mode="template" if os.environ.get("WHATSAPP_TEMPLATE") else "text", message_id=resp.get("messages", [{}])[0].get("id"))
    except (urllib.error.URLError, KeyError, ValueError) as e:
        detail = e.read().decode(errors="replace")[:500] if isinstance(e, urllib.error.HTTPError) else str(e)
        log.warning("WhatsApp send failed: %s", detail)
        result["error"] = "WhatsApp send failed"
    try:
        alert = (
            f"New plan request: {intake['name']} ({intake['business_name']}, {intake['country'] or 'country not given'}) "
            f"wants {service_name}. WhatsApp +{intake['whatsapp']}. Plan: {proposal_url}"
        )
        _post({"messaging_product": "whatsapp", "to": OWNER_NUMBER, "type": "text", "text": {"preview_url": True, "body": alert}})
    except (urllib.error.URLError, KeyError, ValueError) as e:
        log.warning("Owner alert failed: %s", e)
    return result
