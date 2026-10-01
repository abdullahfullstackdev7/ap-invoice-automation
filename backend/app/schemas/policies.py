import uuid
from decimal import Decimal

from app.models.enums import TolerancePolicyScope, UserRole
from app.schemas.base import ORMModel


class TolerancePolicyCreate(ORMModel):
    scope: TolerancePolicyScope
    vendor_id: uuid.UUID | None = None
    category: str | None = None
    qty_pct: Decimal = Decimal("0")
    price_pct: Decimal = Decimal("1")
    price_abs: Decimal = Decimal("1")
    total_abs: Decimal = Decimal("0.02")
    tax_abs: Decimal = Decimal("0.02")


class TolerancePolicyRead(TolerancePolicyCreate):
    id: uuid.UUID


class ApprovalPolicyCreate(ORMModel):
    min_amount: Decimal
    max_amount: Decimal | None = None
    reason_code: str | None = None
    required_role: UserRole
    steps: list[str] = []


class ApprovalPolicyRead(ApprovalPolicyCreate):
    id: uuid.UUID
