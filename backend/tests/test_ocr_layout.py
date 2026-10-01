from app.ocr.layout import reconstruct_lines
from app.ocr.types import BoundingBox, OCRWord


def _word(text: str, x0: float, y0: float, x1: float, y1: float) -> OCRWord:
    return OCRWord(text=text, bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1), conf=0.99, page=1)


def test_reconstruct_lines_groups_same_row_words() -> None:
    words = [
        _word("Invoice", 10, 10, 60, 25),
        _word("No:", 65, 10, 90, 25),
        _word("INV-001", 95, 11, 150, 26),
    ]

    lines = reconstruct_lines(words, page=1)

    assert len(lines) == 1
    assert lines[0].text == "Invoice No: INV-001"


def test_reconstruct_lines_separates_different_rows() -> None:
    words = [
        _word("Header", 10, 10, 60, 25),
        _word("Total: 100", 10, 200, 90, 215),
    ]

    lines = reconstruct_lines(words, page=1)

    assert len(lines) == 2
    assert lines[0].text == "Header"
    assert lines[1].text == "Total: 100"


def test_reconstruct_lines_orders_left_to_right_within_a_line() -> None:
    words = [
        _word("World", 100, 10, 150, 25),
        _word("Hello", 10, 10, 60, 25),
    ]

    lines = reconstruct_lines(words, page=1)

    assert lines[0].text == "Hello World"


def test_reconstruct_lines_empty_input() -> None:
    assert reconstruct_lines([], page=1) == []
