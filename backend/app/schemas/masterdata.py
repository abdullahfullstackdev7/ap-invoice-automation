import uuid
from decimal import Decimal

from app.models.enums import VendorRiskTier, VendorStatus
from app.schemas.base import ORMModel


class VendorCreate(ORMModel):
    code: str
    name: str
    tax_id: str | None = None
    address: str | None = None
    email: str | None = None
    payment_terms_days: int = 30
    discount_pct: Decimal | None = None
    discount_days: int | None = None
    risk_tier: VendorRiskTier = VendorRiskTier.low
    category: str | None = None


class VendorRead(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    name_normalized: str
    tax_id: str | None
    payment_terms_days: int
    discount_pct: Decimal | None
    discount_days: int | None
    risk_tier: VendorRiskTier
    category: str | None
    status: VendorStatus


class ItemCreate(ORMModel):
    sku: str
    description: str
    unit: str
    std_price: Decimal
    category: str


class ItemRead(ORMModel):
    id: uuid.UUID
    sku: str
    description: str
    unit: str
    std_price: Decimal
    category: str
