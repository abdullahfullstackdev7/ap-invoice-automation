import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base
from app.models.masterdata import Item, Vendor


class Repository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def list(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self.session.execute(select(self.model).limit(limit).offset(offset))
        return list(result.scalars().all())

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        return instance


class VendorRepository(Repository[Vendor]):
    model = Vendor

    async def find_by_embedding(self, query_embedding: list[float], limit: int = 5) -> list[Vendor]:
        stmt = (
            select(Vendor)
            .where(Vendor.embedding.is_not(None))
            .order_by(Vendor.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_tax_id(self, tax_id: str) -> Vendor | None:
        result = await self.session.execute(select(Vendor).where(Vendor.tax_id == tax_id))
        return result.scalar_one_or_none()


class ItemRepository(Repository[Item]):
    model = Item

    async def find_by_embedding(self, query_embedding: list[float], limit: int = 5) -> list[Item]:
        stmt = (
            select(Item)
            .where(Item.embedding.is_not(None))
            .order_by(Item.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
