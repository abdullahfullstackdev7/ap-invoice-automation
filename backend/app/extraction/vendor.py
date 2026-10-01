import re

from app.extraction.anchors import _line_starts_with_any_label
from app.extraction.types import ExtractedField
from app.models.enums import ExtractionSource
from app.ocr.types import OCRLine

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
TAX_ID_RE = re.compile(r"\b(?:TAX|VAT|EIN|GST)[\s\-:]*[A-Z0-9\-]{6,20}\b", re.IGNORECASE)

VENDOR_TOP_LINES = 5


def extract_vendor_name(lines: list[OCRLine]) -> ExtractedField[str]:
    """Best-effort vendor name: the first substantive line near the top of
    the page (the logo/letterhead area), skipping anything that looks like
    an email, tax id, or a recognized field label.
    """
    for line in lines[:VENDOR_TOP_LINES]:
        text = line.text.strip()
        if not text or len(text) < 3:
            continue
        if EMAIL_RE.search(text) or TAX_ID_RE.search(text):
            continue
        if _line_starts_with_any_label(line):
            continue
        confidences = [w.conf for w in line.words]
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return ExtractedField[str](
            value=text, confidence=mean_conf, source=ExtractionSource.rules, bbox=line.bbox
        )
    return ExtractedField[str]()


def extract_vendor_email(lines: list[OCRLine]) -> ExtractedField[str]:
    for line in lines:
        match = EMAIL_RE.search(line.text)
        if match:
            return ExtractedField[str](
                value=match.group(0), confidence=0.9, source=ExtractionSource.rules,
                bbox=line.bbox,
            )
    return ExtractedField[str]()


def extract_vendor_tax_id(lines: list[OCRLine]) -> ExtractedField[str]:
    for line in lines:
        match = TAX_ID_RE.search(line.text)
        if match:
            return ExtractedField[str](
                value=match.group(0), confidence=0.85, source=ExtractionSource.rules,
                bbox=line.bbox,
            )
    return ExtractedField[str]()
