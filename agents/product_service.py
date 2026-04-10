# agents/product_service.py
"""
ProductService — بيبحث عن المنتجات في MySQL.

Search Pipeline:
  1. QueryUnderstanding (LLM) → category + English terms + brand
  2. Category-first DB fetch  → narrows to right domain
  3. Token OR search           → each term is an independent ILIKE condition
  4. Relevance scoring         → rank by token hits + rating
  5. Related terms broadening  → if < 5 results
  6. Category fallback         → last resort
"""
import logging
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionFactory, ProductModel
from agents.query_understanding import get_query_understanding

logger = logging.getLogger(__name__)

RELATED_TERMS: dict[str, list[str]] = {
    "ring":         ["ring", "jewelry", "jewelery", "gold", "necklace", "bracelet"],
    "phone":        ["phone", "mobile", "iphone", "samsung", "smartphone"],
    "iphone":       ["iphone", "phone", "apple", "smartphone"],
    "samsung":      ["samsung", "galaxy", "phone", "smartphone"],
    "laptop":       ["laptop", "computer", "notebook", "macbook", "pro"],
    "macbook":      ["macbook", "laptop", "apple", "notebook", "computer"],
    "computer":     ["computer", "laptop", "macbook", "notebook"],
    "shirt":        ["shirt", "clothing", "tshirt", "men's clothing"],
    "jacket":       ["jacket", "shirt", "coat", "clothing", "men's clothing"],
    "jewelry":      ["jewelry", "jewelery", "ring", "gold", "necklace", "earring"],
    "jewelery":     ["jewelery", "jewelry", "ring", "gold", "necklace", "earring"],
    "gold":         ["gold", "ring", "jewelry", "jewelery", "necklace"],
    "earring":      ["earring", "jewelry", "jewelery", "ring"],
    "necklace":     ["necklace", "jewelry", "jewelery", "gold", "ring"],
    "monitor":      ["monitor", "screen", "display", "electronics"],
    "electronics":  ["electronics", "phone", "laptop", "monitor", "tablet"],
    "gaming":       ["gaming", "playstation", "xbox", "electronics"],
    "backpack":     ["backpack", "bag", "clothing"],
    "perfume":      ["perfume", "fragrance", "cologne"],
}


def _row_to_dict(row: ProductModel) -> dict:
    return {
        "id":          row.id,
        "title":       row.title,
        "price":       row.price,
        "category":    row.category,
        "description": row.description,
        "image":       row.image,
        "rating": {
            "rate":  row.rating_rate,
            "count": row.rating_count,
        },
    }


def _score_row(row: ProductModel, terms: list[str]) -> float:
    title = (row.title       or "").lower()
    desc  = (row.description or "").lower()
    cat   = (row.category    or "").lower()
    score = 0.0
    for term in terms:
        t = term.lower()
        if t in title:
            score += 1.0
        if t in desc:
            score += 0.3
        if t in cat:
            score += 0.4
    try:
        score += (float(row.rating_rate) / 5.0) * 0.5
    except Exception:
        pass
    return score


class _MySQLProductService:

    async def _fetch_by_category(
        self, session: AsyncSession, category: str, limit: int
    ) -> list[ProductModel]:
        stmt = (
            select(ProductModel)
            .where(ProductModel.category.ilike(f"%{category}%"))
            .limit(limit)
        )
        return (await session.execute(stmt)).scalars().all()

    async def _fetch_by_terms(
        self, session: AsyncSession, terms: list[str], limit: int
    ) -> list[ProductModel]:
        if not terms:
            return []
        conditions = []
        for term in terms:
            like = f"%{term}%"
            conditions += [
                ProductModel.title.ilike(like),
                ProductModel.description.ilike(like),
                ProductModel.category.ilike(like),
            ]
        stmt = select(ProductModel).where(or_(*conditions)).limit(limit)
        return (await session.execute(stmt)).scalars().all()

    async def _fetch_related(
        self, session: AsyncSession, terms: list[str], seen_ids: set, limit: int
    ) -> list[ProductModel]:
        expanded: list[str] = []
        for term in terms:
            expanded += RELATED_TERMS.get(term.lower(), [])
        expanded = list(dict.fromkeys(expanded))
        if not expanded:
            return []
        extra: list[ProductModel] = []
        rows = await self._fetch_by_terms(session, expanded, limit)
        for r in rows:
            if r.id not in seen_ids:
                extra.append(r)
                seen_ids.add(r.id)
        return extra

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        if not query or not query.strip():
            return []
        try:
            # ── Step 1: LLM understands query ─────────────────────────────────
            qu     = get_query_understanding()
            intent = qu.understand(query)

            category = intent.get("category")
            terms    = intent.get("terms") or []
            brand    = intent.get("brand")

            if brand and brand.lower() not in [t.lower() for t in terms]:
                terms.append(brand.lower())

            logger.info(f"[PS] query='{query}' | category={category} | terms={terms}")

            async with AsyncSessionFactory() as session:
                scored_map: dict[int, tuple[ProductModel, float]] = {}

                # ── Step 2: Category-first ────────────────────────────────────
                if category:
                    for row in await self._fetch_by_category(session, category, limit * 3):
                        scored_map[row.id] = (row, _score_row(row, terms))

                # ── Step 3: Token OR search ───────────────────────────────────
                if len(scored_map) < limit and terms:
                    for row in await self._fetch_by_terms(session, terms, limit * 3):
                        new_score = _score_row(row, terms)
                        if row.id not in scored_map or new_score > scored_map[row.id][1]:
                            scored_map[row.id] = (row, new_score)

                # ── Step 4: Related terms broadening ─────────────────────────
                if len(scored_map) < 5:
                    for row in await self._fetch_related(
                        session, terms, set(scored_map.keys()), limit * 2
                    ):
                        scored_map[row.id] = (row, _score_row(row, terms) * 0.6)

                # ── Step 5: Category fallback ─────────────────────────────────
                if len(scored_map) < 3 and scored_map:
                    first_cat = next(iter(scored_map.values()))[0].category
                    for row in await self._fetch_by_category(session, first_cat, limit):
                        if row.id not in scored_map:
                            scored_map[row.id] = (row, _score_row(row, terms) * 0.3)

                ranked = sorted(scored_map.values(), key=lambda x: x[1], reverse=True)
                result = [_row_to_dict(r) for r, _ in ranked[:limit]]

                if ranked:
                    logger.info(
                        f"[PS] {len(result)} results | "
                        f"top: '{ranked[0][0].title}' score={ranked[0][1]:.2f}"
                    )
                else:
                    logger.warning(f"[PS] No results for '{query}'")
                return result

        except Exception:
            logger.error(f"[PS] Error searching '{query}'", exc_info=True)
            return []

    async def by_category(self, category: str, limit: int = 10) -> list[dict]:
        try:
            async with AsyncSessionFactory() as session:
                rows = await self._fetch_by_category(session, category, limit)
                return [_row_to_dict(r) for r in rows]
        except Exception:
            logger.error(f"[PS] Error in by_category '{category}'", exc_info=True)
            return []

    async def get_product_by_id(self, product_id: int) -> dict | None:
        try:
            async with AsyncSessionFactory() as session:
                row = await session.get(ProductModel, product_id)
                return _row_to_dict(row) if row else None
        except Exception:
            logger.error(f"[PS] Error fetching product {product_id}", exc_info=True)
            return None

    def all_categories(self) -> list[str]:
        return [
            "electronics", "jewelery",
            "men's clothing", "women's clothing",
            "beauty", "fragrances", "furniture", "groceries",
        ]


ProductService = _MySQLProductService()