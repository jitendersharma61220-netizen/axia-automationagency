"""Command line: python -m axia.sales <command>"""

import argparse
import csv
import json
import os
import sys

from axia.core import ai as ai_mod
from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import alerter, make_channels
from axia.core.server import make_handler, serve

from .agent import SalesAgent
from .store import Store


def build(db_path, playbook_path, ai=None, channels=None):
    with open(playbook_path, encoding="utf-8") as f:
        playbook = json.load(f)
    conn = connect(db_path)
    store = Store(conn)
    channels = channels or make_channels()
    approvals = Approvals(conn, "sales")
    outbox = Outbox(approvals, channels, auto_send=playbook.get("auto_send", False))
    alert = alerter(channels, playbook["sales_rep"], "Sales agent alert")
    agent = SalesAgent(store, ai, outbox, playbook, alert)
    return agent, approvals


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.sales")
    p.add_argument("--db", default=os.environ.get("AXIA_SALES_DB", "sales.db"))
    p.add_argument("--playbook", default=os.environ.get(
        "AXIA_SALES_PLAYBOOK", "examples/sales_playbook.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="add a lead")
    add.add_argument("name")
    add.add_argument("--email", default="")
    add.add_argument("--phone", default="")
    add.add_argument("--company", default="")
    add.add_argument("--website", default="")
    add.add_argument("--message", default="")
    add.add_argument("--source", default="manual")
    imp = sub.add_parser("import", help="import leads from CSV "
                                        "(name,email,phone,company,website,message)")
    imp.add_argument("csv_path")
    sub.add_parser("run", help="process new leads and send due follow-ups (run from cron)")
    rep = sub.add_parser("reply", help="a lead replied (paste their message)")
    rep.add_argument("contact", help="their email or phone")
    rep.add_argument("text")
    rep.add_argument("--channel", default="whatsapp")
    sub.add_parser("pending", help="messages waiting for your approval")
    ap = sub.add_parser("approve", help="send a pending message")
    ap.add_argument("id", type=int)
    ap.add_argument("--body", help="send this edited text instead")
    rj = sub.add_parser("reject", help="drop a pending message")
    rj.add_argument("id", type=int)
    show = sub.add_parser("show", help="a lead's profile and conversation")
    show.add_argument("contact")
    sub.add_parser("report", help="pipeline summary")
    srv = sub.add_parser("serve", help="webhook for website leads and WhatsApp replies")
    srv.add_argument("--port", type=int, default=8010)
    args = p.parse_args(argv)

    needs_ai = args.cmd in ("add", "import", "run", "reply", "serve")
    agent, approvals = build(args.db, args.playbook, ai_mod.make_ai() if needs_ai else None)
    store = agent.store

    if args.cmd == "add":
        lead, new = store.add(args.name, args.email, args.phone, args.company,
                              args.website, args.message, args.source)
        print(f"Lead #{lead.id} {'added' if new else 'already exists'}")
        agent.process_new()
    elif args.cmd == "import":
        n = 0
        with open(args.csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    store.add(**{k: row.get(k, "") for k in
                                 ("name", "email", "phone", "company", "website", "message")},
                              source="import")
                    n += 1
                except ValueError as e:
                    print(f"skipped {row}: {e}", file=sys.stderr)
        print(f"Imported {n} leads; processing...")
        agent.process_new()
    elif args.cmd == "run":
        print(f"Processed {agent.process_new()} new leads, sent {agent.run_followups()} follow-ups")
    elif args.cmd == "reply":
        lead = agent.handle_reply(args.contact, args.text, args.channel)
        print(f"{lead.name}: now {lead.stage}")
    elif args.cmd == "pending":
        for item in approvals.pending():
            pl = item["payload"]
            print(f"#{item['id']} {item['summary']}\n{pl['subject'] + chr(10) if pl['subject'] else ''}"
                  f"{pl['body']}\n")
    elif args.cmd == "approve":
        approvals.approve(args.id, {"body": args.body} if args.body else None)
        print("Sent")
    elif args.cmd == "reject":
        approvals.reject(args.id)
        print("Dropped")
    elif args.cmd == "show":
        lead = store.find(args.contact)
        if lead is None:
            sys.exit("No such lead")
        print(agent.profile(lead))
        print(f"Stage: {lead.stage}  Score: {lead.score}")
    elif args.cmd == "report":
        print(json.dumps(agent.report(), indent=2, default=str))
    elif args.cmd == "serve":
        def lead_route(data):
            lead, _ = store.add(**{k: str(data.get(k, "")) for k in
                                   ("name", "email", "phone", "company", "website", "message")},
                                source=str(data.get("source") or "web"))
            agent.process_new()
            return {"id": lead.id}

        def reply_route(data):  # e.g. forwarded email replies
            lead = agent.handle_reply(data["from"], data["text"], data.get("channel", "email"))
            return {"id": lead.id, "stage": lead.stage}

        handler = make_handler({"/lead": lead_route, "/reply": reply_route},
                               on_whatsapp=lambda phone, text: agent.handle_reply(phone, text),
                               verify_token=os.environ.get("AXIA_WA_VERIFY_TOKEN", ""))
        serve(handler, args.port)


if __name__ == "__main__":
    main()
