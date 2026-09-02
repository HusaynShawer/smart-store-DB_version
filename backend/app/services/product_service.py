# app/services/product_service.py
"""ProductAdminService — admin CRUD with automatic semantic embeddings."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import EmbeddingService, get_embedding_service
from app.core.logging import get_logger
from app.db.models import ProductModel
from app.db.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductUpdate

logger = get_logger(__name__)


def product_embedding_text(product: ProductModel | ProductCreate) -> str:
    """Composite text we embed for semantic search (title + category + description)."""
    return f"{product.title} {product.category} {product.description}".strip()


class ProductAdminService:
    def __init__(
        self,
        session: AsyncSession,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._repo = ProductRepository(session)
        self._embeddings = embeddings or get_embedding_service()

    async def create(self, data: ProductCreate) -> ProductModel:
        product = ProductModel(
            title=data.title,
            price=data.price,
            category=data.category,
            description=data.description,
            image=data.image,
            rating_rate=data.rating.rate,
            rating_count=data.rating.count,
        )
        await self._set_embedding(product)
        return await self._repo.add(product)

    async def replace(self, product: ProductModel, data: ProductCreate) -> ProductModel:
        product.title = data.title
        product.price = data.price
        product.category = data.category
        product.description = data.description
        product.image = data.image
        product.rating_rate = data.rating.rate
        product.rating_count = data.rating.count
        await self._set_embedding(product)
        await self._repo.flush()
        return product

    async def patch(self, product: ProductModel, data: ProductUpdate) -> ProductModel:
        changes = data.model_dump(exclude_unset=True)
        if "rating" in changes and changes["rating"] is not None:
            changes["rating_rate"] = data.rating.rate if data.rating else 0
            changes["rating_count"] = data.rating.count if data.rating else 0
            changes.pop("rating")
        for field, value in changes.items():
            setattr(product, field, value)
        await self._set_embedding(product)
        await self._repo.flush()
        return product

    async def delete_all(self) -> int:
        return await self._repo.delete_all()

    async def _set_embedding(self, product: ProductModel) -> None:
        try:
            vector = await self._embeddings.embed_query(product_embedding_text(product))
            if vector:
                product.embedding = vector
        except Exception as exc:
            logger.warning("Embedding skipped for product %s: %s", product.id, exc)