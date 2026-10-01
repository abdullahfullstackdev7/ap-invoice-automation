import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.enums import ExceptionSeverity
from app.models.invoicing import Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.policies import TolerancePolicy
from app.models.procurement import POLine, PurchaseOrder


@dataclass(frozen=True)
class LineMapping:
    invoice_line_id: uuid.UUID
    po_line_id: uuid.UUID | None
    score: float
    method: str


@dataclass(frozen=True)
class MatchContext:
    """Pure data snapshot a rule function reads from. Rules never touch the
    database directly, which is what makes them unit-testable in isolation
    and keeps the Hungarian line-mapping and policy lookups out of their
    way (Plan.md section 7, "Design points").
    """

    invoice: Invoice
    invoice_lines: list[InvoiceLine]
    vendor: Vendor | None
    po: PurchaseOrder | None
    po_lines: list[POLine]
    po_lines_by_id: dict[uuid.UUID, POLine]
    qty_received_by_po_line: dict[uuid.UUID, Decimal]
    line_mappings: list[LineMapping]
    policy: TolerancePolicy
    auto_approve_limit: Decimal
    vendor_price_history: dict[str, list[tuple[date, Decimal]]] = field(default_factory=dict)

    def po_line_for(self, invoice_line_id: uuid.UUID) -> POLine | None:
        for mapping in self.line_mappings:
            if mapping.invoice_line_id == invoice_line_id and mapping.po_line_id is not None:
                return self.po_lines_by_id.get(mapping.po_line_id)
        return None


@dataclass(frozen=True)
class ExceptionDraft:
    reason_code: str
    severity: ExceptionSeverity
    details: dict[str, object]


# Reason codes that stop a clean match entirely, per Plan.md section 7,
# item 7 ("BLOCKED: exact duplicate, or PO closed and vendor mismatch")
# and section 4.4's anomaly table (PO_NOT_FOUND/PO_CLOSED/VENDOR_MISMATCH
# all mean there is nothing valid to match against, unlike a quantity or
# price variance which still has a PO to reconcile against).
BLOCKING_REASON_CODES = frozenset(
    {"DUPLICATE_EXACT", "PO_NOT_FOUND", "PO_CLOSED", "VENDOR_MISMATCH"}
)
