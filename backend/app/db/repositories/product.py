# app/db/repositories/product.py
"""ProductRepository — keyword + vector (pgvector) search and admin CRUD."""
from typing import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ProductModel
from app.db.repositories.base import BaseRepository


class ProductRepository(BaseRepository[ProductModel]):
    model = ProductModel

    # ── Search ───────────────────────────────────────────────────────────────

    async def search_keyword(self, term: str, limit: int = 10) -> list[ProductModel]:
        like = f"%{term}%"
        stmt = (
            select(ProductModel)
            .where(
                or_(
                    ProductModel.title.ilike(like),
                    ProductModel.description.ilike(like),
                    ProductModel.category.ilike(like),
                )
            )
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def search_vector(
        self, query_vector: list[float], top_k: int = 10, max_distance: float = 0.65
    ) -> list[tuple[ProductModel, float]]:
        """Semantic search over the pgvector column (cosine distance).

        Threshold tuned for OpenAI-compatible embeddings (text-embedding-3-small):
        their cosine distances are wider than Cohere's, so 0.65 is a safer cutoff.
        """
        if not query_vector:
            return []
        distance = ProductModel.embedding.cosine_distance(query_vector)
        stmt = (
            select(ProductModel, distance.label("distance"))
            .where(distance <= max_distance)
            .order_by(distance.asc())
            .limit(top_k)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(row[0], float(row[1])) for row in rows]

    async def by_category(self, category: str, limit: int = 10) -> list[ProductModel]:
        stmt = (
            select(ProductModel)
            .where(ProductModel.category.ilike(f"%{category}%"))
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    # ── Admin CRUD ───────────────────────────────────────────────────────────

    async def filtered_list(
        self, q: str | None, category: str | None, skip: int, limit: int
    ) -> tuple[int, list[ProductModel]]:
        stmt = select(ProductModel)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    ProductModel.title.ilike(like),
                    ProductModel.description.ilike(like),
                    ProductModel.category.ilike(like),
                )
            )
        if category:
            stmt = stmt.where(ProductModel.category.ilike(f"%{category}%"))

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