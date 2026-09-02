# app/db/repositories/order.py
"""OrderRepository — create / query orders and admin ops."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrderModel
from app.db.repositories.base import BaseRepository


class OrderRepository(BaseRepository[OrderModel]):
    model = OrderModel

    async def filtered_list(
        self, status: str | None, phone: str | None, skip: int, limit: int
    ) -> tuple[int, list[OrderModel]]:
        stmt = select(OrderModel).order_by(OrderModel.created_at.desc())
        if status:
            stmt = stmt.where(OrderModel.status == status)
        if phone:
            stmt = stmt.where(OrderModel.customer_phone.ilike(f"%{phone}%"))

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