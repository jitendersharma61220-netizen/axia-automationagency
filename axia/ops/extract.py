"""Turns a bill (photo or text) into one structured record.

With AI: Claude reads the bill photo or text (any layout, printed or
handwritten) and fills in every field. Without AI: regular expressions pull
the common fields out of text bills.
"""

import re
from datetime import datetime

FIELDS = ["vendor", "invoice_number", "date", "gstin", "category",
          "items", "subtotal", "tax", "total"]

CATEGORIES = ["Rent", "Electricity & Utilities", "Supplies & Stock", "Equipment",
              "Salaries", "Marketing", "Travel", "Food", "Repairs", "Other"]

BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": "string"},
        "invoice_number": {"type": "string"},
        "date": {"type": "string", "description": "YYYY-MM-DD, empty if unknown"},
        "gstin": {"type": "string", "description": "vendor GSTIN, empty if none"},
        "category": {"type": "string", "enum": CATEGORIES},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "amount": {"type": "number"},
                },
                "required": ["description", "quantity", "amount"],
                "additionalProperties": False,
            },
        },
        "subtotal": {"type": "number"},
        "tax": {"type": "number", "description": "total GST (CGST+SGST+IGST)"},
        "total": {"type": "number"},
    },
    "required": FIELDS,
    "additionalProperties": False,
}

SYSTEM = (
    "You do bookkeeping data entry for a small Indian business. Read the bill and "
    "fill in every field. Amounts are in rupees as plain numbers. Use an empty "
    "string or 0 for anything the bill does not show; never guess a GSTIN or "
    "invoice number. Pick the closest category for the expense."
)

GSTIN_RE = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
INVOICE_RE = re.compile(
    r"(?:invoice|bill|inv)\s*(?:no|number|#)\.?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]*)", re.I)
DATE_RE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\b")
AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d{1,2})?)\s*$", re.I)
TAX_RE = re.compile(r"\b(?:cgst|sgst|igst|gst)\b", re.I)

CATEGORY_WORDS = {
    "Rent": ["rent", "lease"],
    "Electricity & Utilities": ["electricity", "power", "water", "internet", "broadband", "bses", "jio", "airtel"],
    "Supplies & Stock": ["supplies", "stationery", "medicine", "pharma", "stock", "material"],
    "Equipment": ["equipment", "machine", "computer", "laptop", "printer"],
    "Marketing": ["advertis", "printing", "flex", "banner", "marketing"],
    "Travel": ["travel", "petrol", "diesel", "fuel", "uber", "ola", "taxi"],
    "Food": ["restaurant", "food", "cafe", "tea", "snacks"],
    "Repairs": ["repair", "service charge", "maintenance"],
}


def extract(content, ai=None):
    """content: bill text (str) or a list of content blocks (e.g. a photo)."""
    if ai is not None:
        from axia.core.ai import AIError

        try:
            return normalize(ai.ask_json(SYSTEM, content, BILL_SCHEMA))
        except AIError as e:
            if not isinstance(content, str):
                raise ValueError(f"reading a bill photo needs AI: {e}") from e
            print(f"AI unavailable, using text rules: {e}")
    if not isinstance(content, str):
        raise ValueError("reading a bill photo needs AI (set ANTHROPIC_API_KEY)")
    return extract_with_rules(content)


def extract_with_rules(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    gstin = GSTIN_RE.search(text)
    inv = INVOICE_RE.search(text)
    total = tax = 0.0
    for line in lines:
        amount = _amount(line)
        if amount is None:
            continue
        low = line.lower()
        if TAX_RE.search(low) and "total" not in low:
            tax += amount
        elif "total" in low and "sub" not in low:
            total = amount  # the last "total" line is usually the grand total
    lower = text.lower()
    category = next((c for c, words in CATEGORY_WORDS.items()
                     if any(w in lower for w in words)), "Other")
    return normalize({
        "vendor": lines[0] if lines else "",
        "invoice_number": inv.group(1) if inv else "",
        "date": _date(text),
        "gstin": gstin.group(0) if gstin else "",
        "category": category,
        "items": [],
        "subtotal": round(total - tax, 2) if total else 0,
        "tax": round(tax, 2),
        "total": total,
    })


def normalize(record):
    out = {k: record.get(k, "") for k in FIELDS}
    out["items"] = record.get("items") or []
    for k in ("subtotal", "tax", "total"):
        out[k] = float(out[k] or 0)
    if out["category"] not in CATEGORIES:
        out["category"] = "Other"
    return out


def _amount(line):
    m = AMOUNT_RE.search(line)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _date(text):
    m = DATE_RE.search(text)
    if not m:
        return ""
    day, month, year = (int(g) for g in m.groups())
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")  # Indian bills are day-first
    except ValueError:
        return ""
