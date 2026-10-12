# app/db/repositories/base.py
"""Generic async CRUD repository — shared building block for all entities."""
from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Typed async repository with the most common operations."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, obj_id: int | str) -> ModelT | None:
        return await self._session.get(self.model, obj_id)

    async def list(self, skip: int = 0, limit: int = 50) -> list[ModelT]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        return int((await self._session.execute(stmt)).scalar_one())

    async def add(self, instance: ModelT) -> ModelT:
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self._session.delete(instance)
        await self._session.flush()

    async def flush(self) -> None:
        """Persist pending changes without committing the transaction."""
        await self._session.flush()

    async def delete_all(self) -> int:
        from sqlalchemy import delete

        result = await self._session.execute(delete(self.model))
        return result.rowcount