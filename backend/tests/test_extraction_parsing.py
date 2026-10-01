from datetime import date
from decimal import Decimal

from app.extraction.parsing import (
    normalize_invoice_number,
    parse_currency_code,
    parse_date,
    parse_money,
)


def test_parse_money_plain() -> None:
    assert parse_money("192.50") == Decimal("192.50")


def test_parse_money_with_currency_symbol() -> None:
    assert parse_money("$1,234.56") == Decimal("1234.56")


def test_parse_money_european_format() -> None:
    assert parse_money("1.234,56") == Decimal("1234.56")


def test_parse_money_empty_returns_none() -> None:
    assert parse_money("") is None
    assert parse_money("not a number") is None


def test_parse_date_iso() -> None:
    assert parse_date("2026-09-15") == date(2026, 9, 15)


def test_parse_date_slash_format() -> None:
    assert parse_date("09/15/2026") == date(2026, 9, 15)


def test_parse_date_invalid_returns_none() -> None:
    assert parse_date("") is None


def test_parse_currency_code_from_symbol() -> None:
    assert parse_currency_code("$192.50") == "USD"


def test_parse_currency_code_from_iso_code() -> None:
    assert parse_currency_code("Total: 192.50 EUR") == "EUR"


def test_parse_currency_code_none_found() -> None:
    assert parse_currency_code("no currency here") is None


def test_normalize_invoice_number() -> None:
    assert normalize_invoice_number(" inv-2026-0042 ") == "INV-2026-0042"
