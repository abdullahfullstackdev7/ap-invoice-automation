from app.llm.prompts import (
    build_header_prompt,
    build_lines_prompt,
    build_repair_prompt,
    strip_ocr_text,
)
from app.llm.token_estimate import estimate_tokens

# Plan.md section 6, item 5: system prompt under 150 tokens.
MAX_SYSTEM_PROMPT_TOKENS = 150


def test_strip_ocr_text_removes_blank_lines_and_collapses_whitespace() -> None:
    raw = "Invoice No:   INV-001\n\n\nTotal:    192.50\n   \n"
    result = strip_ocr_text(raw)
    assert result == "Invoice No: INV-001\nTotal: 192.50"


def test_header_system_prompt_under_token_budget() -> None:
    system, _ = build_header_prompt("some ocr text")
    assert estimate_tokens(system) < MAX_SYSTEM_PROMPT_TOKENS


def test_lines_system_prompt_under_token_budget() -> None:
    system, _ = build_lines_prompt("some table text")
    assert estimate_tokens(system) < MAX_SYSTEM_PROMPT_TOKENS


def test_header_prompt_user_content_is_the_stripped_ocr_text() -> None:
    _, user = build_header_prompt("Invoice No:   INV-001\n\n")
    assert user == "Invoice No: INV-001"


def test_repair_prompt_includes_previous_output_and_errors() -> None:
    prompt = build_repair_prompt('{"bad": true}', "missing field 'total'")
    assert '{"bad": true}' in prompt
    assert "missing field 'total'" in prompt
