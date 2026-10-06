"""Validate and normalise what a visitor typed into the form."""

import re

from .services import SERVICES

CURRENCIES = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED ", "SAR": "SAR ",
    "AUD": "A$", "CAD": "C$", "SGD": "S$", "ZAR": "R ", "NGN": "₦", "KES": "KSh ",
}

LANGUAGES = ["English", "Hindi", "Hinglish", "Spanish", "Arabic", "French", "Portuguese"]

TEXT_LIMITS = {
    "name": 80,
    "business_name": 120,
    "industry": 120,
    "country": 60,
    "business_description": 1000,
    "main_problem": 1000,
}

# (field, min, max, default) for the numbers that drive the estimate
NUMBER_FIELDS = [
    ("team_size", 1, 100000, 5),
    ("monthly_inquiries", 0, 10_000_000, 300),
    ("avg_order_value", 0, 1_000_000_000, 2000),
    ("hours_per_week", 0, 10000, 20),
    ("hourly_cost", 0, 100000, 200),
    ("conversion_pct", 0.1, 100, 10),
    ("margin_pct", 1, 100, 30),
]


class IntakeError(ValueError):
    pass


def _number(raw, lo, hi, default):
    if raw in (None, ""):
        return default
    try:
        value = float(str(raw).replace(",", ""))
    except ValueError:
        raise IntakeError(f"'{raw}' is not a number")
    if value != value or value < lo or value > hi:  # NaN or out of range
        raise IntakeError(f"{value:g} is outside {lo:g} to {hi:g}")
    return value


def normalise_phone(raw):
    digits = re.sub(r"\D", "", raw or "")
    if not 8 <= len(digits) <= 15:
        raise IntakeError("Please enter your WhatsApp number with country code, for example +1 415 555 0100")
    return digits


def parse(form):
    """Return a clean dict, or raise IntakeError with a message fit to show the visitor."""
    if not isinstance(form, dict):
        raise IntakeError("Expected a JSON object")
    service = form.get("service")
    if service not in SERVICES:
        raise IntakeError("Please pick a service")

    out = {"service": service}
    for field, limit in TEXT_LIMITS.items():
        value = str(form.get(field) or "").strip()
        out[field] = value[:limit]
    for field in ("name", "business_name", "main_problem"):
        if not out[field]:
            raise IntakeError(f"Please fill in {field.replace('_', ' ')}")

    out["whatsapp"] = normalise_phone(form.get("whatsapp"))
    currency = str(form.get("currency") or "USD").upper()
    out["currency"] = currency if currency in CURRENCIES else "USD"
    language = form.get("language") or "English"
    out["language"] = language if language in LANGUAGES else "English"

    for field, lo, hi, default in NUMBER_FIELDS:
        try:
            out[field] = _number(form.get(field), lo, hi, default)
        except IntakeError as e:
            raise IntakeError(f"{field.replace('_', ' ').capitalize()}: {e}")
    return out
