"""The accounts back-office agent: from a vendor bill to a scheduled payment.

For every bill:
1. Read it (Claude: photo, PDF or text into structured data).
2. Check it (code): GSTIN check digit, arithmetic, CGST/SGST vs IGST, our
   GSTIN, duplicates.
3. Match it to the purchase order and goods received (Claude pairs the bill
   lines with PO lines; code compares quantities and rates).
4. Decide (code): clean bills under the auto-approve limit are approved;
   everything else goes to the approver with a short note Claude writes
   explaining what is wrong, plus a drafted query email to the vendor.
5. Approved bills go into the ledger (CSV for Tally / Excel import) and the
   payables list with a due date.
"""

import csv
import json
from datetime import date, timedelta

from axia.core.ai import AIError
from axia.core.approvals import now

from . import checks
from .extract import extract

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    vendor TEXT NOT NULL,
    vendor_gstin TEXT NOT NULL,
    invoice_number TEXT NOT NULL,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    po_number TEXT NOT NULL,
    total REAL NOT NULL,
    data TEXT NOT NULL,
    issues TEXT NOT NULL,
    status TEXT NOT NULL,      -- approved, on_hold, rejected, duplicate, paid
    created_at TEXT NOT NULL,
    paid_at TEXT
);
"""

MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "bill_line": {"type": "integer"},
                    "po_line": {"type": "integer", "description": "-1 if no PO line matches"},
                },
                "required": ["bill_line", "po_line"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["matches"],
    "additionalProperties": False,
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "approver_note": {"type": "string"},
        "vendor_email_subject": {"type": "string"},
        "vendor_email": {"type": "string",
                         "description": "polite query to the vendor; empty if nothing to ask"},
    },
    "required": ["approver_note", "vendor_email_subject", "vendor_email"],
    "additionalProperties": False,
}


def load_purchase_orders(path):
    """PO lines from CSV: po_number,vendor,description,quantity,rate,received_quantity."""
    pos = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pos.setdefault(r["po_number"].strip().upper(), []).append({
                "vendor": r["vendor"], "description": r["description"],
                "quantity": float(r["quantity"]), "rate": float(r["rate"]),
                "received_quantity": float(r.get("received_quantity") or r["quantity"]),
            })
    return pos


class OpsAgent:
    def __init__(self, conn, ai, approvals, outbox, company, purchase_orders, alert, clock=now):
        self.conn = conn
        self.ai = ai
        self.approvals = approvals
        self.outbox = outbox
        self.company = company
        self.pos = purchase_orders
        self.alert = alert
        self.clock = clock
        conn.executescript(SCHEMA)
        approvals.on_approve("bill", lambda p: self._set_status(p["bill_id"], "approved"))

    def process(self, source, content):
        """Run one bill through the whole pipeline. Returns the saved bill row."""
        bill = extract(self.ai, content)
        issues = checks.check_bill(bill, self.company["gstin"])
        if self._duplicate(bill):
            return self._save(source, bill, ["Same vendor and invoice number already entered"],
                              "duplicate")

        po_lines = self.pos.get(bill["po_number"].strip().upper()) if bill["po_number"] else None
        if po_lines is None:
            issues.append(f"No purchase order found ({bill['po_number'] or 'no PO on bill'})")
        else:
            issues += checks.check_po_match(self._match(bill, po_lines), po_lines,
                                            self.company.get("rate_tolerance_pct", 2))

        if not issues and bill["total"] <= self.company.get("auto_approve_limit", 0):
            return self._save(source, bill, [], "approved")
        row = self._save(source, bill, issues, "on_hold")
        self._ask_approver(row, bill, issues)
        return row

    def _match(self, bill, po_lines):
        """Pair bill lines with PO lines. Descriptions rarely match word for word."""
        r = self.ai.ask_json(
            "ops.match",
            "You match lines on a vendor bill to lines on our purchase order. Match by "
            "what the item is, ignoring spelling, pack-size wording and abbreviations. "
            "Each PO line matches at most one bill line. Use -1 when nothing fits.",
            "Bill lines:\n" + "\n".join(f"{i}: {l['description']}"
                                        for i, l in enumerate(bill["lines"]))
            + "\n\nPO lines:\n" + "\n".join(f"{i}: {l['description']}"
                                           for i, l in enumerate(po_lines)),
            MATCH_SCHEMA, effort="low")
        found = {m["bill_line"]: m["po_line"] for m in r["matches"]}
        used = set()
        pairs = []
        for i, line in enumerate(bill["lines"]):
            j = found.get(i, -1)
            ok = 0 <= j < len(po_lines) and j not in used
            used.add(j)
            pairs.append((line, j if ok else None))
        return pairs

    def _ask_approver(self, row, bill, issues):
        total = f"Rs {bill['total']:,.2f}"
        try:
            r = self.ai.ask_json(
                "ops.review",
                f"You are the accounts assistant at {self.company['company']}. Explain a "
                "bill on hold to the approver in 2-4 plain sentences (what is wrong, money at "
                "stake, what you recommend). If the vendor must fix or explain something, "
                "draft a short, polite email to them; otherwise leave it empty.",
                f"Bill: {json.dumps(bill)}\nIssues found:\n- " + "\n- ".join(issues),
                REVIEW_SCHEMA, effort="low")
        except AIError:
            r = {"approver_note": "; ".join(issues), "vendor_email": "",
                 "vendor_email_subject": ""}
        self.approvals.request(
            "bill", f"{bill['vendor']} {bill['invoice_number']} {total}",
            {"bill_id": row["id"], "note": r["approver_note"], "issues": issues},
            ref=row["id"])
        vendor_address = self.company.get("vendor_emails", {}).get(bill["vendor_gstin"])
        if r["vendor_email"] and vendor_address:
            self.outbox.send("email", vendor_address, r["vendor_email"],
                             subject=r["vendor_email_subject"], ref=row["id"], why="vendor query",
                             always_review=True)
        elif r["vendor_email"]:
            # No vendor address on file: keep the draft with the bill for the team.
            self._set_data(row["id"], vendor_query=r["vendor_email"])
        self.alert(f"Bill on hold: {bill['vendor']} {total}. {r['approver_note']}")

    # ----- storage --------------------------------------------------------

    def _duplicate(self, bill):
        return bill["invoice_number"] and self.conn.execute(
            "SELECT 1 FROM bills WHERE lower(vendor_gstin) = lower(?) AND invoice_number = ?"
            " AND status != 'rejected'",
            (bill["vendor_gstin"] or bill["vendor"], bill["invoice_number"])).fetchone()

    def _save(self, source, bill, issues, status):
        due = bill["due_date"] or self._due(bill)
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO bills (source, vendor, vendor_gstin, invoice_number, invoice_date,"
                " due_date, po_number, total, data, issues, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (source, bill["vendor"], bill["vendor_gstin"] or bill["vendor"],
                 bill["invoice_number"], bill["invoice_date"], due, bill["po_number"],
                 bill["total"], json.dumps(bill), json.dumps(issues), status,
                 self.clock().isoformat()))
        return self.bill(cur.lastrowid)

    def _due(self, bill):
        days = bill["payment_terms_days"] or self.company.get("default_payment_days", 30)
        try:
            start = date.fromisoformat(bill["invoice_date"])
        except ValueError:
            start = self.clock().date()
        return (start + timedelta(days=days)).isoformat()

    def _set_status(self, bill_id, status):
        with self.conn:
            self.conn.execute("UPDATE bills SET status = ? WHERE id = ?", (status, bill_id))

    def _set_data(self, bill_id, **extra):
        data = json.loads(self.bill(bill_id)["data"])
        data.update(extra)
        with self.conn:
            self.conn.execute("UPDATE bills SET data = ? WHERE id = ?", (json.dumps(data), bill_id))

    def bill(self, bill_id):
        r = self.conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
        return dict(r) if r else None

    def bills(self, status=None):
        q, args = "SELECT * FROM bills", ()
        if status:
            q, args = q + " WHERE status = ?", (status,)
        return [dict(r) for r in self.conn.execute(q + " ORDER BY due_date, id", args)]

    def reject(self, approval_id):
        item = self.approvals.get(approval_id)
        self.approvals.reject(approval_id)
        self._set_status(item["payload"]["bill_id"], "rejected")

    # ----- payables -------------------------------------------------------

    def payables(self, within_days=7):
        """Approved, unpaid bills that are overdue or due soon."""
        cutoff = (self.clock().date() + timedelta(days=within_days)).isoformat()
        today = self.clock().date().isoformat()
        out = []
        for b in self.bills("approved"):
            if b["due_date"] <= cutoff:
                out.append(dict(b, overdue=b["due_date"] < today))
        return out

    def mark_paid(self, bill_id):
        with self.conn:
            self.conn.execute("UPDATE bills SET status = 'paid', paid_at = ? WHERE id = ?",
                              (self.clock().isoformat(), bill_id))

    def export_ledger(self, path):
        """Approved and paid bills as a purchase register for Tally / Excel."""
        rows = [b for b in self.bills() if b["status"] in ("approved", "paid")]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["invoice_date", "vendor", "vendor_gstin", "invoice_number", "po_number",
                        "taxable_value", "cgst", "sgst", "igst", "total", "due_date", "status"])
            for b in rows:
                d = json.loads(b["data"])
                w.writerow([d["invoice_date"], d["vendor"], d["vendor_gstin"], d["invoice_number"],
                            d["po_number"], d["taxable_value"], d["cgst"], d["sgst"], d["igst"],
                            d["total"], b["due_date"], b["status"]])
        return len(rows)
