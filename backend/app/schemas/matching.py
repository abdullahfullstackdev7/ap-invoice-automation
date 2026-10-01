import uuid
from datetime import datetime
from decimal import Decimal

from app.models.enums import MatchLineStatus, MatchOutcome
from app.schemas.base import ORMModel


class MatchLineResultRead(ORMModel):
    id: uuid.UUID
    invoice_line_id: uuid.UUID | None
    po_line_id: uuid.UUID | None
    qty_inv: Decimal | None
    qty_po: Decimal | None
    qty_recv: Decimal | None
    qty_prev_invoiced: Decimal | None
    price_inv: Decimal | None
    price_po: Decimal | None
    qty_var: Decimal | None
    price_var_pct: Decimal | None
    status: MatchLineStatus


class MatchResultRead(ORMModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    po_id: uuid.UUID | None
    outcome: MatchOutcome
    score: Decimal | None
    run_at: datetime
    line_results: list[MatchLineResultRead] = []
