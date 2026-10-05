"""Command line: python -m axia.hr <command>"""

import argparse
import json
import os

from axia.core import ai as ai_mod
from axia.core.ai import AIError, image_block
from axia.core.approvals import Approvals, Outbox, connect
from axia.core.channels import alerter, make_channels
from axia.core.server import make_handler, serve

from .agent import HiringAgent

DOC_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf")


def read_resume(path):
    if path.lower().endswith(DOC_EXTS):
        return [image_block(path), {"type": "text", "text": "Read this resume."}]
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.hr")
    p.add_argument("--db", default=os.environ.get("AXIA_HR_DB", "hiring.db"))
    p.add_argument("--job", default=os.environ.get("AXIA_HR_JOB", "examples/job.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="score resumes (PDF, photo or .txt)")
    add.add_argument("files", nargs="+")
    rep = sub.add_parser("reply", help="a candidate replied (paste their message)")
    rep.add_argument("contact", help="phone or email")
    rep.add_argument("text")
    sub.add_parser("ranking", help="all candidates by score")
    sub.add_parser("pending", help="rejection messages waiting for HR")
    ap = sub.add_parser("approve")
    ap.add_argument("id", type=int)
    rj = sub.add_parser("reject")
    rj.add_argument("id", type=int)
    srv = sub.add_parser("serve", help="WhatsApp webhook for candidate replies")
    srv.add_argument("--port", type=int, default=8020)
    args = p.parse_args(argv)

    with open(args.job, encoding="utf-8") as f:
        job = json.load(f)
    conn = connect(args.db)
    channels = make_channels()
    approvals = Approvals(conn, "hr")
    needs_ai = args.cmd in ("add", "reply", "serve")
    agent = HiringAgent(conn, ai_mod.make_ai() if needs_ai else None,
                        Outbox(approvals, channels), channels, job,
                        alerter(channels, job["interviewer"], "Interview booked"))

    if args.cmd == "add":
        for path in args.files:
            try:
                c = agent.add_resume(read_resume(path))
            except (OSError, ValueError, AIError) as e:
                print(f"{path}: skipped ({e})")
                continue
            print(f"{path}: {c['name']} scored {c['score']} -> {c['stage']}")
    elif args.cmd == "reply":
        c = agent.handle_reply(args.contact, args.text)
        print(f"{c['name']}: now {c['stage']}")
    elif args.cmd == "ranking":
        for c in agent.ranking():
            when = f" on {c['interview_at'][:16]}" if c["interview_at"] else ""
            print(f"{c['score']:>3}  {c['name']:<25} {c['stage']}{when}")
    elif args.cmd == "pending":
        for item in approvals.pending():
            print(f"#{item['id']} {item['summary']}\n   {item['payload']['body']}")
    elif args.cmd == "approve":
        approvals.approve(args.id)
        print("Sent")
    elif args.cmd == "reject":
        approvals.reject(args.id)
        print("Dropped")
    elif args.cmd == "serve":
        handler = make_handler({}, on_whatsapp=agent.handle_reply,
                               verify_token=os.environ.get("AXIA_WA_VERIFY_TOKEN", ""))
        serve(handler, args.port)


if __name__ == "__main__":
    main()
