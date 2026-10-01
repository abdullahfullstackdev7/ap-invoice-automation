from app.ocr.types import BoundingBox, OCRLine, OCRWord


def _split_word(word: OCRWord) -> list[OCRWord]:
    parts = word.text.split()
    if len(parts) <= 1:
        return [word]

    total_chars = sum(len(p) for p in parts) or 1
    x_span = word.bbox.x1 - word.bbox.x0
    cursor = word.bbox.x0
    tokens = []
    for part in parts:
        part_width = x_span * (len(part) / total_chars)
        tokens.append(
            OCRWord(
                text=part,
                bbox=BoundingBox(
                    x0=cursor, y0=word.bbox.y0, x1=cursor + part_width, y1=word.bbox.y1
                ),
                conf=word.conf,
                page=word.page,
            )
        )
        cursor += part_width
    return tokens


def retokenize_line(line: OCRLine) -> OCRLine:
    """Some OCR engines (RapidOCR among them) detect text in phrase-level
    boxes rather than one box per word - a single "word" might already be
    "Invoice No: INV-2026-0042". Label-proximity matching needs real word
    boundaries, so each OCR word is split on whitespace here, with its
    bounding box divided proportionally by character count. This is an
    approximation (monospacing is assumed within a blob) but is accurate
    enough for anchor and column matching, and is a no-op for engines that
    already return one box per word.
    """
    tokens: list[OCRWord] = []
    for word in line.words:
        tokens.extend(_split_word(word))
    return OCRLine(text=line.text, words=tokens, bbox=line.bbox, page=line.page)


def retokenize_lines(lines: list[OCRLine]) -> list[OCRLine]:
    return [retokenize_line(line) for line in lines]
