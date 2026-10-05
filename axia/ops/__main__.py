"""Command line: python -m axia.ops <command>"""

import argparse
import json
import os

from axia.core import ai as ai_mod
from axia.core.ai import AIError, image_block
from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import alerter, make_channels

from .agent import OpsAgent, load_purchase_orders

DOC_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf")


def read_bill(path):
    if path.lower().endswith(DOC_EXTS):
        return [image_block(path), {"type": "text", "text": "Read this bill."}]
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.ops")
    p.add_argument("--db", default=os.environ.get("AXIA_OPS_DB", "ops.db"))
    p.add_argument("--company", default=os.environ.get(
        "AXIA_OPS_COMPANY", "examples/ops_company.json"))
    p.add_argument("--pos", default=os.environ.get(
        "AXIA_OPS_POS", "examples/purchase_orders.csv"), help="purchase orders CSV")
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="process bills (photos, PDFs or .txt)")
    add.add_argument("files", nargs="+")
    sub.add_parser("bills", help="all bills and their status")
    sub.add_parser("pending", help="bills on hold waiting for approval")
    ap = sub.add_parser("approve", help="approve a bill on hold")
    ap.add_argument("id", type=int)
    rj = sub.add_parser("reject", help="reject a bill on hold")
    rj.add_argument("id", type=int)
    pay = sub.add_parser("payables", help="bills due soon or overdue")
    pay.add_argument("--days", type=int, default=7)
    paid = sub.add_parser("paid", help="mark a bill as paid")
    paid.add_argument("bill_id", type=int)
    ex = sub.add_parser("ledger", help="export the purchase register CSV")
    ex.add_argument("--out", default="purchase_register.csv")
    args = p.parse_args(argv)

    with open(args.company, encoding="utf-8") as f:
        company = json.load(f)
    conn = connect(args.db)
    channels = make_channels()
    approvals = Approvals(conn, "ops")
    agent = OpsAgent(conn, ai_mod.make_ai() if args.cmd == "add" else None, approvals,
                     Outbox(approvals, channels), company, load_purchase_orders(args.pos),
                     alerter(channels, company["approver"], "Bill on hold"))

    if args.cmd == "add":
        for path in args.files:
            try:
                b = agent.process(os.path.basename(path), read_bill(path))
            except (OSError, ValueError, AIError) as e:
                print(f"{path}: not processed ({e})")
                continue
            print(f"{path}: {b['vendor']} Rs {b['total']:,.2f} -> {b['status']}")
            for issue in json.loads(b["issues"]):
                print(f"   - {issue}")
    elif args.cmd == "bills":
        for b in agent.bills():
            print(f"#{b['id']} {b['invoice_date']} {b['vendor']} {b['invoice_number']} "
                  f"Rs {b['total']:,.2f} due {b['due_date']} [{b['status']}]")
    elif args.cmd == "pending":
        for item in approvals.pending():
            if item["kind"] == "bill":
                print(f"#{item['id']} {item['summary']}\n   {item['payload']['note']}")
            else:
                pl = item["payload"]
                print(f"#{item['id']} {item['summary']}\n   {pl['subject']}\n   {pl['body']}")
    elif args.cmd == "approve":
        approvals.approve(args.id)
        print("Approved")
    elif args.cmd == "reject":
        item = approvals.get(args.id)
        if item and item["kind"] == "bill":
            agent.reject(args.id)
        else:
            approvals.reject(args.id)
        print("Rejected")
    elif args.cmd == "payables":
        total = 0
        for b in agent.payables(args.days):
            total += b["total"]
            flag = "OVERDUE " if b["overdue"] else ""
            print(f"#{b['id']} {flag}due {b['due_date']} {b['vendor']} Rs {b['total']:,.2f}")
        print(f"Total to pay: Rs {total:,.2f}")
    elif args.cmd == "paid":
        agent.mark_paid(args.bill_id)
        print("Marked paid")
    elif args.cmd == "ledger":
        print(f"Exported {agent.export_ledger(args.out)} bills to {args.out}")


if __name__ == "__main__":
    main()
