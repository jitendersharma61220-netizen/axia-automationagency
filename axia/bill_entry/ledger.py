"""CSV ledger of bills: one row per bill, opens in Excel or Google Sheets."""

import csv
import os
from collections import defaultdict

from .extract import FIELDS

COLUMNS = ["file"] + FIELDS


def append(path, source, record):
    """Add a bill to the ledger. Returns False if this bill is already there."""
    if is_duplicate(path, record):
        return False
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    row = dict(record, file=source)
    row["items"] = "; ".join(
        f"{i['description']} x{i['quantity']:g} = {i['amount']:.2f}" for i in record["items"])
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow(row)
    return True


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_duplicate(path, record):
    """Same vendor + invoice number (or same vendor, date and total) = same bill."""
    for r in rows(path):
        if r["vendor"].lower() != record["vendor"].lower():
            continue
        if record["invoice_number"] and r["invoice_number"] == record["invoice_number"]:
            return True
        if (not record["invoice_number"] and r["date"] == record["date"]
                and float(r["total"] or 0) == record["total"]):
            return True
    return False


def summary(path):
    """Spend per month and category: {(month, category): total}."""
    totals = defaultdict(float)
    for r in rows(path):
        month = r["date"][:7] or "unknown"
        totals[(month, r["category"])] += float(r["total"] or 0)
    return dict(sorted(totals.items()))
