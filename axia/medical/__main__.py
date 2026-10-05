"""Command line: python -m axia.medical <command>"""

import argparse
import json
import os

from axia.core import ai as ai_mod
from axia.core.ai import image_block
from axia.core.approvals import Approvals, connect
from axia.core.channels import alerter, make_channels

from .agent import ClinicAssistant

DOC_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.medical")
    p.add_argument("--db", default=os.environ.get("AXIA_MEDICAL_DB", "clinic.db"))
    p.add_argument("--clinic", default=os.environ.get("AXIA_CLINIC", "examples/clinic.json"))
    sub = p.add_subparsers(dest="cmd", required=True)
    pt = sub.add_parser("patient", help="add or update a patient")
    pt.add_argument("name")
    pt.add_argument("phone")
    pt.add_argument("--age", type=int)
    pt.add_argument("--sex", default="")
    pt.add_argument("--allergies", default="")
    pt.add_argument("--conditions", default="")
    pt.add_argument("--language", default="English", help="e.g. Hindi, Hinglish, Tamil")
    v = sub.add_parser("visit", help="draft a visit note from a consultation transcript")
    v.add_argument("phone")
    v.add_argument("transcript_file")
    lab = sub.add_parser("lab", help="read a lab report and draft the patient explanation")
    lab.add_argument("phone")
    lab.add_argument("report_file", help="PDF, photo or text")
    sub.add_parser("pending", help="drafts waiting for the doctor")
    ap = sub.add_parser("approve", help="doctor approves a draft")
    ap.add_argument("id", type=int)
    ap.add_argument("--edit", help="JSON replacing fields, e.g. '{\"note\": {...}}'")
    rj = sub.add_parser("reject")
    rj.add_argument("id", type=int)
    sub.add_parser("reminders", help="send due reminders (run every 15 minutes from cron)")
    args = p.parse_args(argv)

    with open(args.clinic, encoding="utf-8") as f:
        clinic = json.load(f)
    conn = connect(args.db)
    channels = make_channels()
    approvals = Approvals(conn, "medical")
    needs_ai = args.cmd in ("visit", "lab")
    assistant = ClinicAssistant(conn, ai_mod.make_ai() if needs_ai else None, approvals,
                                channels, clinic,
                                alerter(channels, clinic["doctor_contact"], "Clinic alert"))

    if args.cmd == "patient":
        pat = assistant.add_patient(args.name, args.phone, args.age, args.sex, args.allergies,
                                    args.conditions, args.language)
        print(f"Patient #{pat['id']} {pat['name']} saved")
    elif args.cmd == "visit":
        with open(args.transcript_file, encoding="utf-8") as f:
            visit_id = assistant.draft_visit(args.phone, f.read())
        print(f"Draft note #{visit_id} is waiting for the doctor: python -m axia.medical pending")
    elif args.cmd == "lab":
        path = args.report_file
        if path.lower().endswith(DOC_EXTS):
            content = [image_block(path), {"type": "text", "text": "Read this lab report."}]
        else:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        _, results = assistant.read_lab_report(args.phone, content)
        for r in results:
            mark = "" if r["status"] == "normal" else f"  <-- {r['status'].upper()}"
            print(f"{r['test']}: {r['value']:g} {r['unit']}{mark}")
    elif args.cmd == "pending":
        for item in approvals.pending():
            print(f"#{item['id']} {item['summary']}")
            print(json.dumps({k: v for k, v in item["payload"].items()
                              if k not in ("visit_id", "report_id")},
                             indent=2, ensure_ascii=False))
    elif args.cmd == "approve":
        approvals.approve(args.id, json.loads(args.edit) if args.edit else None)
        print("Approved and sent to the patient")
    elif args.cmd == "reject":
        approvals.reject(args.id)
        print("Rejected")
    elif args.cmd == "reminders":
        print(f"Sent {assistant.send_due_reminders()} reminders")


if __name__ == "__main__":
    main()
