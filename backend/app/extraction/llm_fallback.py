import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.extraction.parsing import parse_date, parse_money
from app.extraction.types import ExtractedField, InvoiceExtract, LineItemExtract
from app.extraction.validator import ValidationResult
from app.llm.prompts import build_header_prompt, build_lines_prompt
from app.llm.protocol import LLMProvider
from app.llm.router import Router
from app.llm.schemas import LLMHeaderOutput, LLMLinesOutput
from app.models.enums import ExtractionSource

HEADER_FIELD_PARSERS = {
    "invoice_no": lambda v: v.strip() or None,
    "invoice_date": parse_date,
    "due_date": parse_date,
    "po_reference": lambda v: v.strip() or None,
    "currency": lambda v: v.strip().upper() or None,
    "subtotal": parse_money,
    "tax": parse_money,
    "discount": parse_money,
    "total": parse_money,
}


def _needs_header_llm(result: ValidationResult) -> bool:
    header_fields = set(InvoiceExtract.HEADER_FIELDS)
    return bool(header_fields & (set(result.failing_fields) | set(result.low_confidence_fields)))


def _needs_lines_llm(result: ValidationResult) -> bool:
    return "lines" in result.failing_fields or any(
        f.startswith("lines[") for f in result.failing_fields
    )


async def apply_llm_fallback(
    extract: InvoiceExtract,
    validation: ValidationResult,
    ocr_text: str,
    table_text: str,
    router: Router,
    *,
    invoice_id: uuid.UUID | None = None,
) -> InvoiceExtract:
    """Fills in only the fields the rules extractor could not produce
    confidently, per Plan.md section 6: "send only what failed", one LLM
    call per invoice at most for header and one for lines.
    """
    settings = get_settings()

    if _needs_header_llm(validation):
        system, user = build_header_prompt(ocr_text)
        header_result = await router.extract(
            system,
            user,
            LLMHeaderOutput,
            max_tokens=settings.llm_max_tokens_header,
            invoice_id=invoice_id,
        )
        if header_result is not None:
            _merge_header(extract, header_result)

    if _needs_lines_llm(validation):
        system, user = build_lines_prompt(table_text)
        lines_result = await router.extract(
            system,
            user,
            LLMLinesOutput,
            max_tokens=settings.llm_max_tokens_lines,
            invoice_id=invoice_id,
        )
        if lines_result is not None and lines_result.lines:
            extract.lines = [
                LineItemExtract(
                    line_no=idx,
                    description=ExtractedField[str](
                        value=item.description, confidence=0.7, source=ExtractionSource.llm_text
                    ),
                    qty=_llm_money_field(item.qty),
                    unit_price=_llm_money_field(item.unit_price),
                    amount=_llm_money_field(item.amount),
                )
                for idx, item in enumerate(lines_result.lines, start=1)
            ]

    return extract


def _llm_money_field(raw: str) -> ExtractedField[Decimal]:
    value = parse_money(raw)
    if value is None:
        return ExtractedField[Decimal]()
    return ExtractedField[Decimal](value=value, confidence=0.7, source=ExtractionSource.llm_text)


def _merge_header(extract: InvoiceExtract, llm_output: LLMHeaderOutput) -> None:
    for field_name, parser in HEADER_FIELD_PARSERS.items():
        current = getattr(extract, field_name)
        if current.is_present:
            continue  # only fill gaps; never override a rules-extracted value
        raw_value = getattr(llm_output, field_name)
        if not raw_value:
            continue
        parsed_value = parser(raw_value)
        if parsed_value is None:
            continue
        setattr(
            extract,
            field_name,
            ExtractedField(value=parsed_value, confidence=0.7, source=ExtractionSource.llm_text),
        )


def build_router_from_settings(session: AsyncSession) -> Router | None:
    """Only builds a router when at least one provider has an API key
    configured, so the pipeline degrades to needs_review instantly in
    environments without keys rather than making slow doomed network calls.
    """
    from app.core.settings import get_settings
    from app.llm.gemini_provider import get_gemini_provider
    from app.llm.groq_provider import get_groq_provider

    settings = get_settings()
    if not settings.groq_api_key and not settings.gemini_api_key:
        return None

    providers: dict[str, LLMProvider] = {
        "groq": get_groq_provider(),
        "gemini": get_gemini_provider(),
    }
    return Router(session, providers, settings.llm_primary, settings.llm_secondary)
