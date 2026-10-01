"""Simulated bank-file generation for a payment batch, Plan.md section 8.

No real bank connection: a flat CSV in a conventional NACHA-adjacent shape
(payee, amount, date, reference), enough to round-trip through a bank's
import screen in a demo without implementing an actual payment rail.
"""

import csv
import io
from decimal import Decimal

from app.models.invoicing import Invoice
from app.models.masterdata import Vendor
from app.models.payments import Payment

CSV_HEADER = ["payment_id", "invoice_id", "vendor_name", "vendor_code", "amount", "scheduled_date"]


def render_batch_csv(rows: list[tuple[Payment, Invoice, Vendor]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADER)
    for payment, invoice, vendor in rows:
        writer.writerow(
            [
                str(payment.id),
                str(invoice.id),
                vendor.name,
                vendor.code,
                str(payment.amount),
                payment.scheduled_date.isoformat(),
            ]
        )
    return buf.getvalue().encode("utf-8")


def batch_total(payments: list[Payment]) -> Decimal:
    return sum((p.amount for p in payments), Decimal("0"))
