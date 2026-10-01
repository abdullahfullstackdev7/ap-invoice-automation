from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.enums import VendorRiskTier
from app.schemas.masterdata import ItemCreate, VendorCreate


def test_vendor_create_uses_decimal_for_money() -> None:
    vendor = VendorCreate(
        code="V00001",
        name="Acme Supplies Inc",
        discount_pct=Decimal("2.5"),
        risk_tier=VendorRiskTier.medium,
    )
    assert vendor.discount_pct == Decimal("2.5")
    assert isinstance(vendor.discount_pct, Decimal)


def test_item_create_requires_std_price() -> None:
    with pytest.raises(ValidationError):
        ItemCreate(sku="SKU1", description="Widget", unit="each", category="IT hardware")  # type: ignore[call-arg]


def test_item_create_rejects_non_numeric_price() -> None:
    with pytest.raises(ValidationError):
        ItemCreate(
            sku="SKU1",
            description="Widget",
            unit="each",
            std_price="not-a-number",
            category="IT hardware",
        )
