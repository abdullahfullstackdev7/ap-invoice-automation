from app.extraction.anchors import (
    extract_currency_field,
    extract_date_field,
    extract_money_field,
    extract_string_field,
)
from app.extraction.table import extract_line_items
from app.extraction.tokenize import retokenize_lines
from app.extraction.types import InvoiceExtract
from app.extraction.vendor import extract_vendor_email, extract_vendor_name, extract_vendor_tax_id
from app.ocr.types import OCRDocumentResult


def run_rules_extraction(ocr_result: OCRDocumentResult) -> InvoiceExtract:
    all_lines = retokenize_lines([line for page in ocr_result.pages for line in page.lines])

    return InvoiceExtract(
        invoice_no=extract_string_field(all_lines, "invoice_no"),
        invoice_date=extract_date_field(all_lines, "invoice_date"),
        due_date=extract_date_field(all_lines, "due_date"),
        po_reference=extract_string_field(all_lines, "po_reference"),
        vendor_name=extract_vendor_name(all_lines),
        vendor_email=extract_vendor_email(all_lines),
        vendor_tax_id=extract_vendor_tax_id(all_lines),
        currency=extract_currency_field(all_lines),
        subtotal=extract_money_field(all_lines, "subtotal"),
        tax=extract_money_field(all_lines, "tax"),
        discount=extract_money_field(all_lines, "discount"),
        total=extract_money_field(all_lines, "total"),
        lines=extract_line_items(all_lines),
    )
