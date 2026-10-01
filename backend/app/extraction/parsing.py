import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from dateutil import parser as dateutil_parser
from price_parser import Price

_CURRENCY_SYMBOLS = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_CURRENCY_CODE_RE = re.compile(r"\b(USD|EUR|GBP|JPY|CAD|AUD)\b", re.IGNORECASE)

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%b %d, %Y", "%d %b %Y")


def parse_money(text: str) -> Decimal | None:
    """Locale-aware money parsing. Keeps sign, drops currency symbols and
    thousands separators, and never returns a float - only Decimal.
    """
    if not text:
        return None
    price = Price.fromstring(text)
    if price.amount is not None:
        return Decimal(str(price.amount))

    cleaned = re.sub(r"[^\d.,\-]", "", text).strip()
    if not cleaned:
        return None
    # Normalize "1.234,56" (European) vs "1,234.56" (US) by checking which
    # separator appears last, since that one is the decimal point.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Ambiguous: treat as thousands separator unless it looks like a
        # two-digit decimal (e.g. "12,50").
        if re.search(r",\d{2}$", cleaned):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_currency_code(text: str) -> str | None:
    match = _CURRENCY_CODE_RE.search(text)
    if match:
        return match.group(1).upper()
    for symbol, code in _CURRENCY_SYMBOLS.items():
        if symbol in text:
            return code
    return None


def parse_date(text: str) -> date | None:
    if not text or not text.strip():
        return None
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        parsed: datetime = dateutil_parser.parse(text, fuzzy=True, dayfirst=False)
        return parsed.date()
    except (ValueError, OverflowError):
        return None


def normalize_invoice_number(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().upper())
