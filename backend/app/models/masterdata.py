from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, LargeBinary, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin
from app.models.enums import VendorRiskTier, VendorStatus

EMBEDDING_DIM = 384


class Vendor(UUIDPKMixin, Base):
    __tablename__ = "vendors"

    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    name_normalized: Mapped[str] = mapped_column(String(300))
    tax_id: Mapped[str | None] = mapped_column(String(50))
    address: Mapped[str | None] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(320))
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    discount_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    discount_days: Mapped[int | None] = mapped_column(Integer)
    risk_tier: Mapped[VendorRiskTier] = mapped_column(String(10), default=VendorRiskTier.low)
    category: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[VendorStatus] = mapped_column(String(10), default=VendorStatus.active)
    bank_account_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    __table_args__ = (
        Index(
            "ix_vendors_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_vendors_name_normalized_trgm",
            "name_normalized",
            postgresql_using="gin",
            postgresql_ops={"name_normalized": "gin_trgm_ops"},
        ),
    )


class Item(UUIDPKMixin, Base):
    __tablename__ = "items"

    sku: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(String(500))
    unit: Mapped[str] = mapped_column(String(20))
    std_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    category: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))

    __table_args__ = (
        Index(
            "ix_items_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
