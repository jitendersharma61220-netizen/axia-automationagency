"""Reads a bill (photo, PDF or text) into structured data with Claude."""

SYSTEM = (
    "You do accounts-payable data entry for an Indian company. Read the vendor's "
    "bill exactly as printed. Amounts are rupees as plain numbers. Dates are "
    "YYYY-MM-DD (Indian bills are day-first). Use an empty string or 0 for anything "
    "not printed on the bill; never guess a GSTIN, invoice number or PO number."
)

_S = {"type": "string"}
_N = {"type": "number"}

BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": _S,
        "vendor_gstin": _S,
        "buyer_gstin": _S,
        "invoice_number": _S,
        "invoice_date": _S,
        "due_date": {"type": "string", "description": "YYYY-MM-DD if printed, else empty"},
        "payment_terms_days": {"type": "integer", "description": "0 if not printed"},
        "po_number": _S,
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"description": _S, "quantity": _N, "rate": _N, "amount": _N},
                "required": ["description", "quantity", "rate", "amount"],
                "additionalProperties": False,
            },
        },
        "taxable_value": _N,
        "cgst": _N,
        "sgst": _N,
        "igst": _N,
        "total": _N,
    },
    "required": ["vendor", "vendor_gstin", "buyer_gstin", "invoice_number", "invoice_date",
                 "due_date", "payment_terms_days", "po_number", "lines", "taxable_value",
                 "cgst", "sgst", "igst", "total"],
    "additionalProperties": False,
}


def extract(ai, content):
    """content: the bill text, or content blocks (photo / PDF + instruction)."""
    return ai.ask_json("ops.extract", SYSTEM, content, BILL_SCHEMA)
