"""Command line: python -m axia.lead_followup <command>"""

import argparse
import csv
import sys

from . import engine, webhook
from .config import Settings
from .mailer import make_mailer
from .store import Store


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.lead_followup")
    sub = p.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="add one lead and send the instant reply")
    add.add_argument("name")
    add.add_argument("email")
    add.add_argument("--phone", default="")
    add.add_argument("--message", default="")
    add.add_argument("--source", default="manual")

    imp = sub.add_parser("import", help="import leads from a CSV (name,email,phone,message)")
    imp.add_argument("csv_path")

    sub.add_parser("run", help="send all due follow-ups (run this from cron)")

    rep = sub.add_parser("replied", help="stop follow-ups for a lead who answered")
    rep.add_argument("email")

    sub.add_parser("list", help="show all leads")

    srv = sub.add_parser("serve", help="start the webhook that receives leads")
    srv.add_argument("--port", type=int, default=8000)

    args = p.parse_args(argv)
    settings = Settings.from_env()
    store = Store(settings.db_path)
    mailer = make_mailer(settings)

    if args.cmd == "add":
        lead = engine.handle_new_lead(
            store, mailer, settings, name=args.name, email=args.email,
            phone=args.phone, message=args.message, source=args.source,
        )
        print(f"Lead #{lead.id} saved")
    elif args.cmd == "import":
        n = 0
        with open(args.csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    engine.handle_new_lead(
                        store, mailer, settings,
                        name=row.get("name", ""), email=row.get("email", ""),
                        phone=row.get("phone", ""), message=row.get("message", ""),
                        source="import",
                    )
                    n += 1
                except ValueError as e:
                    print(f"skipped row {row}: {e}", file=sys.stderr)
        print(f"Imported {n} leads")
    elif args.cmd == "run":
        print(f"Sent {engine.run_due(store, mailer, settings)} follow-ups")
    elif args.cmd == "replied":
        print("Stopped" if store.mark_replied(args.email) else "No such lead")
    elif args.cmd == "list":
        for lead in store.all_leads():
            status = "replied" if lead.replied else f"sent steps {sorted(store.sent_steps(lead.id))}"
            print(f"#{lead.id} {lead.name} <{lead.email}> {lead.source} {status}")
    elif args.cmd == "serve":
        webhook.serve(store, mailer, settings, port=args.port)


if __name__ == "__main__":
    main()
