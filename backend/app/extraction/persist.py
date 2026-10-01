from app.extraction.parsing import normalize_invoice_number
from app.extraction.types import InvoiceExtract
from app.models.invoicing import Invoice, InvoiceLine


def apply_extract_to_invoice(invoice: Invoice, extract: InvoiceExtract) -> list[InvoiceLine]:
    """Copies the extraction result onto the Invoice row's header columns
    and returns InvoiceLine rows to add (not added here, so the caller
    controls the session/transaction).
    """
    invoice.invoice_no = (
        normalize_invoice_number(extract.invoice_no.value) if extract.invoice_no.value else None
    )
    invoice.invoice_date = extract.invoice_date.value
    invoice.due_date = extract.due_date.value
    invoice.po_number_ref = extract.po_reference.value
    invoice.currency = extract.currency.value or invoice.currency
    invoice.subtotal = extract.subtotal.value
    invoice.tax = extract.tax.value
    invoice.discount = extract.discount.value
    invoice.total = extract.total.value

    lines = [
        InvoiceLine(
            invoice_id=invoice.id,
            line_no=line.line_no,
            description=line.description.value or "",
            qty=line.qty.value or 0,
            unit_price=line.unit_price.value or 0,
            amount=line.amount.value or 0,
        )
        for line in extract.lines
        if line.description.value
    ]
    return lines


def extract_to_json(extract: InvoiceExtract) -> dict[str, object]:
    return extract.model_dump(mode="json")
