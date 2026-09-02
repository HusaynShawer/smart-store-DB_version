# app/services/search_service.py
"""
Hybrid product search (Strategy pattern):
  semantic (pgvector · Cohere) → keyword (ILIKE + Arabic→English) → category fallback

Each returned product is enriched with the store(s) that sell it, so the agent
and the frontend see shop_id/shop_name/shop_phone/product_url in one payload.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import EmbeddingService, get_embedding_service
from app.core.logging import get_logger
from app.db.models import ProductModel
from app.db.repositories.product import ProductRepository
from app.db.repositories.store import StoreRepository
from app.schemas.serializers import product_to_dict
from app.services.location_service import sort_stores_by_distance

logger = get_logger(__name__)

AR_TO_EN: dict[str, str] = {
    "تيشيرت": "shirt", "تي شيرت": "shirt", "قميص": "shirt", "تيشرت": "shirt",
    "جاكيت": "jacket", "جاكت": "jacket", "جاكيتة": "jacket",
    "ملابس": "clothing", "هدوم": "clothing", "لبس": "clothing",
    "شاشة": "monitor", "شاشه": "monitor", "شاشات": "monitor",
    "شاشه كمبيوتر": "monitor", "شاشة كمبيوتر": "monitor",
    "مونيتور": "monitor", "منيتور": "monitor",
    "إلكترونيات": "electronics", "الكترونيات": "electronics", "الكترونيك": "electronics",
    "هارد": "drive", "هارد ديسك": "drive", "هارد خارجي": "drive",
    "تخزين": "ssd", "اس اس دي": "ssd",
    "مجوهرات": "jewelery", "جواهر": "jewelery",
    "خاتم": "ring", "دبلة": "ring", "خواتم": "ring",
    "حلق": "earring", "حلقان": "earring",
    "ذهب": "gold", "فضة": "silver",
    "لابتوب": "laptop", "موبايل": "phone",
    "ايفون": "phone", "آيفون": "phone", "سامسونج": "samsung",
    "أبيض": "white", "ابيض": "white", "أسود": "black", "اسود": "black",
    "حقيبة": "backpack", "شنطة": "backpack",
    "العاب": "gaming", "جيمينج": "gaming", "جيمنج": "gaming",
    "سوني": "playstation", "بلايستيشن": "playstation",
    "ماسكارا": "mascara", "مكياج": "makeup", "عطر": "perfume",
    "كريم": "cream", "عناية": "skincare",
}

RELATED_TERMS: dict[str, list[str]] = {
    "ring": ["ring", "jewelry", "jewelery", "gold", "necklace", "bracelet"],
    "phone": ["phone", "mobile", "iphone", "samsung", "smartphone"],
    "laptop": ["laptop", "computer", "notebook", "pc"],
    "shirt": ["shirt", "clothing", "tshirt", "jacket"],
    "jacket": ["jacket", "shirt", "clothing"],
    "jewelery": ["jewelery", "jewelry", "ring", "gold", "necklace", "earring"],
    "jewelry": ["jewelry", "jewelery", "ring", "gold", "necklace", "earring"],
    "gold": ["gold", "ring", "jewelry", "jewelery", "necklace"],
    "earring": ["earring", "jewelry", "jewelery", "ring", "gold"],
    "necklace": ["necklace", "jewelry", "jewelery", "gold", "ring"],
    "monitor": ["monitor", "screen", "display", "electronics"],
    "electronics": ["electronics", "phone", "laptop", "monitor", "tablet"],
}


def translate(query: str) -> str:
    q = query.lower().strip()
    for ar in sorted(AR_TO_EN, key=len, reverse=True):
        if ar in q:
            q = q.replace(ar, AR_TO_EN[ar])
    return q


class SearchService:
    """Combine semantic + keyword + category strategy into one API."""

    def __init__(
        self,
        session: AsyncSession,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self._products = ProductRepository(session)
        self._stores = StoreRepository(session)
        self._embeddings = embeddings or get_embedding_service()

    # ── Public API ───────────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 6) -> list[dict]:
        """Hybrid search enriched with store info."""
        results = await self._hybrid(query, limit)
        return await self._enrich(results, query)

    async def by_category(self, category: str, limit: int = 6) -> list[dict]:
        rows = await self._products.by_category(category, limit)
        return await self._enrich([product_to_dict(r) for r in rows], category)

    async def search_nearby(
        self, query: str, lat: float, lon: float, limit: int = 6
    ) -> list[dict]:
        """Products sorted by their nearest store's distance."""
        results = await self._hybrid(query, limit)
        return await self._enrich_nearby(results, query, lat, lon)

    # ── Hybrid strategy ──────────────────────────────────────────────────────

    async def _hybrid(self, query: str, limit: int) -> list[dict]:
        query = query.strip()
        seen: dict[int, dict] = {}

        semantic = await self._semantic(query)
        for item in semantic:
            seen.setdefault(item["id"], item)
            if len(seen) >= limit:
                break

        keyword = await self._keyword(query)
        for item in keyword:
            seen.setdefault(item["id"], item)
            if len(seen) >= limit:
                break

        if len(seen) < min(limit, 5) and seen:
            first = next(iter(seen.values()))
            category_rows = await self._products.by_category(first["category"], limit)
            for row in category_rows:
                if row.id not in seen:
                    seen[row.id] = product_to_dict(row)
                if len(seen) >= limit:
                    break

        return list(seen.values())[:limit]

    async def _semantic(self, query: str, top_k: int = 6) -> list[dict]:
        try:
            vector = await self._embeddings.embed_query(query)
        except Exception as exc:
            logger.warning("Semantic search skipped (%s)", exc)
            return []
        hits = await self._products.search_vector(vector, top_k=top_k)
        return [product_to_dict(row) for row, _ in hits]

    async def _keyword(self, query: str, limit: int = 10) -> list[dict]:
        translated = translate(query)
        tokens = [t for t in translated.replace(",", " ").split() if t.strip()]
        if not tokens:
            tokens = [query.strip().lower()]
        seen: dict[int, dict] = {}
        for token in tokens:
            for row in await self._products.search_keyword(token, limit):
                seen.setdefault(row.id, product_to_dict(row))

        if len(seen) < 5:
            for token in tokens:
                for related in RELATED_TERMS.get(token, []):
                    for row in await self._products.search_keyword(related, limit):
                        seen.setdefault(row.id, product_to_dict(row))
                    if len(seen) >= 10:
                        break
        return list(seen.values())

    # ── Store enrichment ─────────────────────────────────────────────────────

    async def _stores_for(self, query: str) -> list[dict]:
        from app.schemas.serializers import store_to_dict

        translated = translate(query)
        terms = [t.strip() for t in translated.replace(",", " ").split() if t.strip()]
        stores: list[dict] = []
        for term in terms[:2]:
            rows = await self._stores.get_stores_by_product(term)
            if rows:
                stores = [store_to_dict(r) for r in rows]
                break
        if not stores:
            rows = await self._stores.list()
            stores = [store_to_dict(r) for r in rows]
        return stores

    def _attach_store(self, product: dict, stores: list[dict], index: int) -> dict:
        if not stores:
            return product
        store = stores[index % len(stores)]
        enriched = dict(product)
        enriched.update(
            {
                "shop_id": store["id"],
                "shop_name": store["name"],
                "shop_governorate": store["governorate"],
                "shop_phone": store.get("phone"),
                "product_url": (
                    product.get("image")
                    or f"https://store.zaki.com/products/{product.get('id')}"
                ),
            }
        )
        return enriched

    async def _enrich(self, products: list[dict], query: str) -> list[dict]:
        if not products:
            return []
        stores = await self._stores_for(query)
        return [self._attach_store(p, stores, i) for i, p in enumerate(products)]

    async def _enrich_nearby(
        self, products: list[dict], query: str, lat: float, lon: float
    ) -> list[dict]:
        if not products:
            return []
        stores = sort_stores_by_distance(await self._stores_for(query), lat, lon)
        enriched = []
        for i, product in enumerate(products):
            enriched.append(self._attach_store(product, stores, i))
            if stores:
                store = stores[i % len(stores)]
                enriched[-1]["shop_distance"] = store.get("distance_km")
        return enriched