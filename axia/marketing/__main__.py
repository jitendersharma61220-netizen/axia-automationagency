"""Command line: python -m axia.marketing <command>"""

import argparse
import json
import os
from datetime import date

from axia.core import ai as ai_mod
from axia.core.approvals import Approvals, connect

from .engine import MarketingEngine


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.marketing")
    p.add_argument("--db", default=os.environ.get("AXIA_MARKETING_DB", "marketing.db"))
    p.add_argument("--brand", default=os.environ.get(
        "AXIA_MARKETING_BRAND", "examples/marketing_brand.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan", help="research and plan a campaign")
    pl.add_argument("goal")
    pl.add_argument("--start", type=date.fromisoformat, default=date.today())
    pl.add_argument("--weeks", type=int, default=4)
    show = sub.add_parser("show", help="print a campaign plan")
    show.add_argument("campaign", type=int)
    cr = sub.add_parser("create", help="write all content for a campaign")
    cr.add_argument("campaign", type=int)
    sub.add_parser("pending", help="content waiting for approval")
    ap = sub.add_parser("approve", help="approve content (optionally with edited fields)")
    ap.add_argument("id", type=int)
    ap.add_argument("--edit", help='JSON of fields to change, e.g. \'{"caption": "..."}\'')
    rj = sub.add_parser("reject")
    rj.add_argument("id", type=int)
    ex = sub.add_parser("export", help="approved content as a posting calendar CSV")
    ex.add_argument("campaign", type=int)
    ex.add_argument("--out", default="calendar.csv")
    an = sub.add_parser("analyze", help="read results CSV and recommend changes")
    an.add_argument("campaign", type=int)
    an.add_argument("metrics_csv", help="columns: date,channel,spend,impressions,clicks,"
                                        "leads,sales,revenue")
    args = p.parse_args(argv)

    with open(args.brand, encoding="utf-8") as f:
        brand = json.load(f)
    conn = connect(args.db)
    approvals = Approvals(conn, "marketing")
    needs_ai = args.cmd in ("plan", "create", "analyze")
    engine = MarketingEngine(conn, ai_mod.make_ai() if needs_ai else None, approvals, brand)

    if args.cmd == "plan":
        cid = engine.plan(args.goal, args.start, args.weeks)
        print(f"Campaign #{cid} planned. Next: python -m axia.marketing show {cid}")
    elif args.cmd == "show":
        print(json.dumps(engine.campaign(args.campaign)["plan"], indent=2, ensure_ascii=False))
    elif args.cmd == "create":
        print(f"Wrote {engine.create_content(args.campaign)} pieces. "
              "Review them: python -m axia.marketing pending")
    elif args.cmd == "pending":
        for item in approvals.pending():
            body = {k: v for k, v in item["payload"].items() if k != "content_id"}
            print(f"#{item['id']} {item['summary']}\n"
                  f"{json.dumps(body, indent=2, ensure_ascii=False)}\n")
    elif args.cmd == "approve":
        approvals.approve(args.id, json.loads(args.edit) if args.edit else None)
        print("Approved")
    elif args.cmd == "reject":
        approvals.reject(args.id)
        print("Rejected")
    elif args.cmd == "export":
        print(f"Exported {engine.export(args.campaign, args.out)} posts to {args.out}")
    elif args.cmd == "analyze":
        a = engine.analyze(args.campaign, args.metrics_csv)
        print(a["summary"])
        for title, key in (("Working", "working"), ("Not working", "not_working"),
                           ("Do next", "actions")):
            print(f"\n{title}:")
            for line in a[key]:
                print(f"  - {line}")
        print("\nNew budget split: " + ", ".join(
            f"{ch} {share:.0%}" for ch, share in a["new_split"].items()))


if __name__ == "__main__":
    main()
