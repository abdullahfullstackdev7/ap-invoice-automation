import re
from datetime import date
from decimal import Decimal

from app.extraction.parsing import parse_currency_code, parse_date, parse_money
from app.extraction.types import ExtractedField
from app.models.enums import ExtractionSource
from app.ocr.types import BoundingBox, OCRLine, OCRWord

# Each label is tried as a token sequence matched against consecutive words
# on a line, longest first so "invoice number" matches before "invoice".
FIELD_LABELS: dict[str, list[str]] = {
    "invoice_no": ["invoice number", "invoice no", "invoice #", "inv no", "inv#"],
    "invoice_date": ["invoice date", "date of issue", "date"],
    "due_date": ["due date", "payment due", "pay by"],
    "po_reference": [
        "purchase order number",
        "po number",
        "po reference",
        "po ref",
        "po no",
        "po#",
    ],
    "subtotal": ["subtotal", "sub total", "sub-total", "net amount"],
    "tax": ["sales tax", "vat", "gst", "tax"],
    "discount": ["discount"],
    "total": ["grand total", "amount due", "balance due", "total due", "total"],
}

_TOKEN_CLEAN_RE = re.compile(r"[^a-z0-9#]+")


def _clean_token(text: str) -> str:
    return _TOKEN_CLEAN_RE.sub("", text.lower())


def _label_matches_at(words: list[OCRWord], start: int, label_tokens: list[str]) -> int:
    """Returns the number of words consumed if label_tokens match starting
    at words[start], else 0.
    """
    idx = start
    for token in label_tokens:
        if idx >= len(words):
            return 0
        if _clean_token(words[idx].text) != token:
            return 0
        idx += 1
    return idx - start


def _union_bbox(words: list[OCRWord]) -> BoundingBox | None:
    if not words:
        return None
    return BoundingBox(
        x0=min(w.bbox.x0 for w in words),
        y0=min(w.bbox.y0 for w in words),
        x1=max(w.bbox.x1 for w in words),
        y1=max(w.bbox.y1 for w in words),
    )


def _mean_conf(words: list[OCRWord]) -> float:
    return sum(w.conf for w in words) / len(words) if words else 0.0


def find_label_value_words(
    lines: list[OCRLine], label_phrases: list[str]
) -> list[OCRWord] | None:
    """Label proximity search: finds the first line containing one of the
    label phrases and returns the words that follow it, using the OCR
    word geometry (not a flat text regex over the whole page).
    """
    tokenized_labels = [[_clean_token(t) for t in phrase.split()] for phrase in label_phrases]

    for line_idx, line in enumerate(lines):
        words = line.words
        for label_tokens in tokenized_labels:
            for start in range(len(words)):
                consumed = _label_matches_at(words, start, label_tokens)
                if consumed == 0:
                    continue
                value_words = words[start + consumed :]
                # Drop a leading bare colon/dash token, e.g. "Invoice No: 123"
                while value_words and _clean_token(value_words[0].text) in ("", ":", "-"):
                    value_words = value_words[1:]
                if value_words:
                    return value_words
                # Label matched but nothing follows on this line: the value
                # is very likely on the next line (common in tighter layouts).
                if line_idx + 1 < len(lines):
                    next_words = lines[line_idx + 1].words
                    if next_words and not _line_starts_with_any_label(lines[line_idx + 1]):
                        return next_words
                return None
    return None


def _line_starts_with_any_label(line: OCRLine) -> bool:
    for label_phrases in FIELD_LABELS.values():
        for phrase in label_phrases:
            tokens = [_clean_token(t) for t in phrase.split()]
            if _label_matches_at(line.words, 0, tokens) > 0:
                return True
    return False


def extract_string_field(lines: list[OCRLine], field: str) -> ExtractedField[str]:
    words = find_label_value_words(lines, FIELD_LABELS[field])
    if not words:
        return ExtractedField[str]()
    text = " ".join(w.text for w in words).strip()
    if not text:
        return ExtractedField[str]()
    return ExtractedField[str](
        value=text, confidence=_mean_conf(words), source=ExtractionSource.rules,
        bbox=_union_bbox(words),
    )


def extract_date_field(lines: list[OCRLine], field: str) -> ExtractedField[date]:
    words = find_label_value_words(lines, FIELD_LABELS[field])
    if not words:
        return ExtractedField[date]()
    text = " ".join(w.text for w in words).strip()
    value = parse_date(text)
    if value is None:
        return ExtractedField[date]()
    return ExtractedField[date](
        value=value, confidence=_mean_conf(words), source=ExtractionSource.rules,
        bbox=_union_bbox(words),
    )


def extract_money_field(lines: list[OCRLine], field: str) -> ExtractedField[Decimal]:
    words = find_label_value_words(lines, FIELD_LABELS[field])
    if not words:
        return ExtractedField[Decimal]()
    text = " ".join(w.text for w in words).strip()
    value = parse_money(text)
    if value is None:
        return ExtractedField[Decimal]()
    return ExtractedField[Decimal](
        value=value, confidence=_mean_conf(words), source=ExtractionSource.rules,
        bbox=_union_bbox(words),
    )


def extract_currency_field(lines: list[OCRLine]) -> ExtractedField[str]:
    for line in lines:
        code = parse_currency_code(line.text)
        if code:
            return ExtractedField[str](
                value=code, confidence=0.9, source=ExtractionSource.rules, bbox=line.bbox
            )
    return ExtractedField[str]()
