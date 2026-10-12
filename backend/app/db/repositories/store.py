# app/db/repositories/store.py
"""StoreRepository — store/vendor lookup and admin CRUD."""
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import StoreModel
from app.db.repositories.base import BaseRepository


class StoreRepository(BaseRepository[StoreModel]):
    model = StoreModel

    async def by_governorate(self, governorate: str) -> list[StoreModel]:
        stmt = select(StoreModel).where(
            StoreModel.governorate.ilike(f"%{governorate}%")
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def filtered_list(
        self, governorate: str | None, q: str | None, skip: int, limit: int
    ) -> tuple[int, list[StoreModel]]:
        stmt = select(StoreModel)
        if governorate:
            stmt = stmt.where(StoreModel.governorate.ilike(f"%{governorate}%"))
        if q:
            stmt = stmt.where(StoreModel.name.ilike(f"%{q}%"))

        total = int(
            (
                await self._session.execute(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).scalar_one()
        )
        items = list(
            (await self._session.execute(stmt.offset(skip).limit(limit))).scalars().all()
        )
        return total, items

    async def get_stores_by_product(self, product_query: str) -> list[StoreModel]:
        """Stores whose catalog (products_csv) contains the query keyword."""
        q = product_query.lower().strip()
        stmt = select(StoreModel).where(StoreModel.products_csv.ilike(f"%{q}%"))
        rows = list((await self._session.execute(stmt)).scalars().all())
        if not rows:  # fallback: every store
            return await self.list()
        return rows