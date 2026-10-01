from decimal import Decimal

from app.extraction.parsing import parse_money
from app.extraction.types import ExtractedField, LineItemExtract
from app.models.enums import ExtractionSource
from app.ocr.types import OCRLine, OCRWord

HEADER_KEYWORDS = {
    "description": ["description", "item", "desc"],
    "qty": ["qty", "quantity"],
    "unit_price": ["price", "unit price", "rate", "unit cost"],
    "amount": ["amount", "total", "line total"],
}
STOP_KEYWORDS = ("subtotal", "sub total", "sub-total", "total", "tax", "balance due")
MIN_HEADER_MATCHES = 2


def _find_header_line(lines: list[OCRLine]) -> tuple[int, dict[str, float]] | None:
    """Returns (line_index, {column_name: x_anchor}) for the best header
    row match, or None if no line looks like a table header.
    """
    for idx, line in enumerate(lines):
        lowered = line.text.lower()
        column_anchors: dict[str, float] = {}
        for column, keywords in HEADER_KEYWORDS.items():
            for word in line.words:
                if any(kw in word.text.lower() for kw in keywords) or any(
                    kw == lowered for kw in keywords
                ):
                    column_anchors.setdefault(column, word.bbox.x0)
        # Fall back to substring search across the whole line if per-word
        # matching missed a multi-word keyword like "unit price".
        for column, keywords in HEADER_KEYWORDS.items():
            if column in column_anchors:
                continue
            for kw in keywords:
                if kw in lowered:
                    pos_char = lowered.index(kw)
                    approx_x = line.bbox.x0 + (pos_char / max(len(lowered), 1)) * (
                        line.bbox.x1 - line.bbox.x0
                    )
                    column_anchors[column] = approx_x
                    break

        if len(column_anchors) >= MIN_HEADER_MATCHES:
            return idx, column_anchors
    return None


def _assign_column(word: OCRWord, boundaries: list[tuple[str, float]]) -> str:
    best_column = boundaries[0][0]
    best_distance = float("inf")
    for column, anchor_x in boundaries:
        distance = abs(word.bbox.x0 - anchor_x)
        if distance < best_distance:
            best_distance = distance
            best_column = column
    return best_column


def _is_stop_line(line: OCRLine) -> bool:
    lowered = line.text.lower().strip()
    return any(lowered.startswith(kw) for kw in STOP_KEYWORDS)


def extract_line_items(lines: list[OCRLine]) -> list[LineItemExtract]:
    header = _find_header_line(lines)
    if header is None:
        return []

    header_idx, column_anchors = header
    boundaries = sorted(column_anchors.items(), key=lambda kv: kv[1])

    items: list[LineItemExtract] = []
    line_no = 0
    for line in lines[header_idx + 1 :]:
        if not line.words:
            continue
        if _is_stop_line(line):
            break

        columns: dict[str, list[OCRWord]] = {col: [] for col, _ in boundaries}
        for word in line.words:
            column = _assign_column(word, boundaries)
            columns[column].append(word)

        description_words = columns.get("description", [])
        qty_words = columns.get("qty", [])
        price_words = columns.get("unit_price", [])
        amount_words = columns.get("amount", [])

        if not description_words and not amount_words:
            continue

        qty_value = parse_money(" ".join(w.text for w in qty_words)) if qty_words else None
        price_value = parse_money(" ".join(w.text for w in price_words)) if price_words else None
        amount_value = (
            parse_money(" ".join(w.text for w in amount_words)) if amount_words else None
        )

        if qty_value is None and price_value is None and amount_value is None:
            continue

        line_no += 1

        def _field(
            words: list[OCRWord], value: Decimal | None
        ) -> ExtractedField[Decimal]:
            if not words or value is None:
                return ExtractedField[Decimal]()
            conf = sum(w.conf for w in words) / len(words)
            return ExtractedField[Decimal](
                value=value, confidence=conf, source=ExtractionSource.rules
            )

        items.append(
            LineItemExtract(
                line_no=line_no,
                description=ExtractedField[str](
                    value=" ".join(w.text for w in description_words).strip() or None,
                    confidence=(
                        sum(w.conf for w in description_words) / len(description_words)
                        if description_words
                        else 0.0
                    ),
                    source=ExtractionSource.rules,
                ),
                qty=_field(qty_words, qty_value),
                unit_price=_field(price_words, price_value),
                amount=_field(amount_words, amount_value),
            )
        )

    return items
