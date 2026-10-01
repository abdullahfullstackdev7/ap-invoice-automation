import uuid
from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin
from app.models.enums import TolerancePolicyScope, UserRole


class TolerancePolicy(UUIDPKMixin, Base):
    __tablename__ = "tolerance_policies"

    scope: Mapped[TolerancePolicyScope] = mapped_column(String(10))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    category: Mapped[str | None] = mapped_column(String(100))
    qty_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    price_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=1)
    price_abs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=1)
    total_abs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0.02)
    tax_abs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0.02)


class ApprovalPolicy(UUIDPKMixin, Base):
    __tablename__ = "approval_policies"

    min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reason_code: Mapped[str | None] = mapped_column(String(50))
    required_role: Mapped[UserRole] = mapped_column(String(30))
    steps: Mapped[list[str]] = mapped_column(ARRAY(String(30)), default=list)
