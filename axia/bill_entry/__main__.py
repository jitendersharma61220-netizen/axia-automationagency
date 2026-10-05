"""Command line: python -m axia.bill_entry <command>"""

import argparse
import os

from axia.ai import image_block, make_ai

from . import extract, ledger

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def read_bill(path):
    if path.lower().endswith(IMAGE_EXTS):
        return [image_block(path), {"type": "text", "text": "Read this bill."}]
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m axia.bill_entry")
    p.add_argument("--ledger", default=os.environ.get("AXIA_LEDGER_PATH", "bills.csv"))
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="read bills (photos or .txt) into the ledger")
    add.add_argument("files", nargs="+")
    sub.add_parser("summary", help="spend per month and category")

    args = p.parse_args(argv)
    if args.cmd == "add":
        ai = make_ai()
        for path in args.files:
            try:
                record = extract.extract(read_bill(path), ai)
            except (OSError, ValueError) as e:
                print(f"{path}: skipped ({e})")
                continue
            if ledger.append(args.ledger, os.path.basename(path), record):
                print(f"{path}: {record['vendor']} Rs {record['total']:.2f} ({record['category']})")
            else:
                print(f"{path}: already in the ledger")
    elif args.cmd == "summary":
        for (month, category), total in ledger.summary(args.ledger).items():
            print(f"{month}  {category:<25} Rs {total:,.2f}")


if __name__ == "__main__":
    main()
