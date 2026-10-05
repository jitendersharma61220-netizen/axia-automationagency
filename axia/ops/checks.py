"""Rule checks an accountant does on every bill, done in code (no AI).

Each check returns a list of issues in plain words; an empty list means the
bill passed.
"""

import re

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
TOLERANCE = 1.0  # rupees of rounding allowed in totals


def gstin_valid(gstin):
    """Format and check-digit test for an Indian GSTIN."""
    gstin = (gstin or "").strip().upper()
    if not GSTIN_RE.match(gstin):
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        product = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36] == gstin[14]


def check_bill(bill, company_gstin):
    issues = []
    if not bill["vendor_gstin"]:
        issues.append("Vendor GSTIN missing: input tax credit cannot be claimed")
    elif not gstin_valid(bill["vendor_gstin"]):
        issues.append(f"Vendor GSTIN {bill['vendor_gstin']} is not valid (check digit fails)")
    if bill["buyer_gstin"] and bill["buyer_gstin"].upper() != company_gstin.upper():
        issues.append(f"Bill is addressed to GSTIN {bill['buyer_gstin']}, not ours")
    if not bill["invoice_number"]:
        issues.append("Invoice number missing")

    lines_total = sum(l["amount"] for l in bill["lines"])
    for l in bill["lines"]:
        if abs(l["quantity"] * l["rate"] - l["amount"]) > TOLERANCE:
            issues.append(f"Line '{l['description']}': {l['quantity']:g} x {l['rate']:.2f} "
                          f"is not {l['amount']:.2f}")
    if bill["lines"] and abs(lines_total - bill["taxable_value"]) > TOLERANCE:
        issues.append(f"Lines add up to {lines_total:.2f} but taxable value is "
                      f"{bill['taxable_value']:.2f}")
    tax = bill["cgst"] + bill["sgst"] + bill["igst"]
    if abs(bill["taxable_value"] + tax - bill["total"]) > TOLERANCE:
        issues.append(f"Taxable value + GST = {bill['taxable_value'] + tax:.2f} "
                      f"but bill total is {bill['total']:.2f}")

    # Same state: CGST + SGST. Different states: IGST. Wrong type = no credit.
    if gstin_valid(bill["vendor_gstin"]) and company_gstin:
        same_state = bill["vendor_gstin"][:2] == company_gstin[:2]
        if same_state and bill["igst"]:
            issues.append("IGST charged on a same-state purchase; should be CGST + SGST")
        if not same_state and (bill["cgst"] or bill["sgst"]):
            issues.append("CGST/SGST charged on an inter-state purchase; should be IGST")
        if bill["cgst"] and abs(bill["cgst"] - bill["sgst"]) > TOLERANCE:
            issues.append("CGST and SGST should be equal")
    return issues


def check_po_match(pairs, po_lines, rate_tolerance_pct):
    """Three-way match: bill vs purchase order vs goods received.

    `pairs` maps bill line -> PO line index (from Claude's matching step).
    """
    issues = []
    for bill_line, po_index in pairs:
        if po_index is None:
            issues.append(f"'{bill_line['description']}' is not on the purchase order")
            continue
        po = po_lines[po_index]
        limit = po["rate"] * (1 + rate_tolerance_pct / 100)
        if bill_line["rate"] > limit + 0.005:
            issues.append(f"'{bill_line['description']}': billed at {bill_line['rate']:.2f}, "
                          f"PO rate is {po['rate']:.2f}")
        if bill_line["quantity"] > po["quantity"]:
            issues.append(f"'{bill_line['description']}': billed {bill_line['quantity']:g}, "
                          f"ordered only {po['quantity']:g}")
        if bill_line["quantity"] > po["received_quantity"]:
            issues.append(f"'{bill_line['description']}': billed {bill_line['quantity']:g}, "
                          f"received only {po['received_quantity']:g}")
    return issues
