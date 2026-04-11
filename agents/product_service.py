"""
ProductService — بيبحث عن المنتجات في MySQL.

Enhanced Arabic search with:
- Arabic text normalization
- Fuzzy matching using SequenceMatcher
- Synonym-based secondary search
"""

import logging
from difflib import SequenceMatcher
from typing import List

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionFactory, ProductModel
from config.settings import get_settings
from config.models_config import SEARCH_FUZZY_THRESHOLD, SEARCH_MIN_RESULTS, SEARCH_MAX_RESULTS
from agents.query_understanding import get_query_understanding
from agents.arabic_normalizer import normalize, normalize_for_database

settings = get_settings()
logger = logging.getLogger(__name__)

RELATED_TERMS: dict[str, list[str]] = {
    "ring": ["ring", "jewelry", "jewelery", "gold", "necklace", "bracelet"],
    "phone": ["phone", "mobile", "iphone", "samsung", "smartphone"],
    "iphone": ["iphone", "phone", "apple", "smartphone"],
    "samsung": ["samsung", "galaxy", "phone", "smartphone"],
    "laptop": ["laptop", "computer", "notebook", "macbook", "pro"],
    "macbook": ["macbook", "laptop", "apple", "notebook", "computer"],
    "computer": ["computer", "laptop", "macbook", "notebook"],
    "shirt": ["shirt", "clothing", "tshirt", "men's clothing"],
    "jacket": ["jacket", "shirt", "coat", "clothing", "men's clothing"],
    "jewelry": ["jewelry", "jewelery", "ring", "gold", "necklace", "earring"],
    "jewelery": ["jewelery", "jewelry", "ring", "gold", "necklace", "earring"],
    "gold": ["gold", "ring", "jewelry", "jewelery", "necklace"],
    "earring": ["earring", "jewelry", "jewelery", "ring"],
    "necklace": ["necklace", "jewelry", "jewelery", "gold", "ring"],
    "monitor": ["monitor", "screen", "display", "electronics"],
    "electronics": ["electronics", "phone", "laptop", "monitor", "tablet"],
    "gaming": ["gaming", "playstation", "xbox", "electronics"],
    "backpack": ["backpack", "bag", "clothing"],
    "perfume": ["perfume", "fragrance", "cologne"],
}


def _calculate_fuzzy_score(query: str, title: str) -> float:
    """Calculate fuzzy match score between query and product title."""
    if not query or not title:
        return 0.0
    
    query_lower = query.lower()
    title_lower = title.lower()
    
    query_tokens = query_lower.split()
    title_tokens = title_lower.split()
    
    max_ratio = 0.0
    
    # Compare full strings
    max_ratio = max(max_ratio, SequenceMatcher(None, query_lower, title_lower).ratio())
    
    # Compare individual tokens
    for q_token in query_tokens:
        for t_token in title_tokens:
            ratio = SequenceMatcher(None, q_token, t_token).ratio()
            max_ratio = max(max_ratio, ratio)
    
    return max_ratio


def _row_to_dict(row: ProductModel) -> dict:
    """Convert ProductModel row to dictionary."""
    return {
        "id": row.id,
        "title": row.title,
        "price": row.price,
        "category": row.category,
        "description": row.description,
        "image": row.image,
        "rating": {
            "rate": row.rating_rate,
            "count": row.rating_count,
        },
    }


def _score_row(row: ProductModel, terms: list[str], query_normalized: str = "") -> float:
    """Calculate relevance score for a product row."""
    title = (row.title or "").lower()
    desc = (row.description or "").lower()
    cat = (row.category or "").lower()
    score = 0.0
    
    # Exact term matching
    for term in terms:
        t = term.lower()
        if t in title:
            score += 1.0
        if t in desc:
            score += 0.3
        if t in cat:
            score += 0.4
    
    # Rating bonus
    try:
        score += (float(row.rating_rate) / 5.0) * 0.5
    except Exception:
        pass
    
    # Fuzzy matching bonus
    if query_normalized:
        fuzzy_score = _calculate_fuzzy_score(query_normalized, row.title or "")
        if fuzzy_score >= SEARCH_FUZZY_THRESHOLD:
            score += 0.4 + (fuzzy_score - SEARCH_FUZZY_THRESHOLD) * 1.33
    
    return score


class _MySQLProductService:
    """Async MySQL product search service with Arabic support."""

    async def _fetch_by_category(
        self, session: AsyncSession, category: str, limit: int
    ) -> list[ProductModel]:
        """Fetch products by category (case-insensitive partial match)."""
        stmt = (
            select(ProductModel)
            .where(ProductModel.category.ilike(f"%{category}%"))
            .limit(limit)
        )
        return (await session.execute(stmt)).scalars().all()

    async def _fetch_by_terms(
        self, session: AsyncSession, terms: list[str], limit: int
    ) -> list[ProductModel]:
        """Fetch products matching any term in title, description, or category."""
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

    async def _fetch_by_synonyms(
        self, session: AsyncSession, synonyms: list[str], limit: int
    ) -> list[ProductModel]:
        """Fetch products using Arabic synonyms against normalized columns."""
        if not synonyms:
            return []
        
        conditions = []
        for synonym in synonyms:
            normalized_syn = normalize_for_database(synonym)
            like = f"%{normalized_syn}%"
            conditions += [
                ProductModel.title.ilike(like),
                ProductModel.description.ilike(like),
            ]
        
        stmt = select(ProductModel).where(or_(*conditions)).limit(limit)
        return (await session.execute(stmt)).scalars().all()

    async def _fetch_related(
        self, session: AsyncSession, terms: list[str], seen_ids: set, limit: int
    ) -> list[ProductModel]:
        """Fetch related products based on RELATED_TERMS mapping."""
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

    async def search(self, query: str, limit: int = SEARCH_MAX_RESULTS) -> list[dict]:
        """Main search method with Arabic normalization and fuzzy matching."""
        if not query or not query.strip():
            return []
        
        try:
            query_normalized = normalize(query)
            
            qu = get_query_understanding()
            intent = qu.understand(query)

            category = intent.get("category")
            terms = intent.get("terms") or []
            synonyms = intent.get("synonyms") or []
            brand = intent.get("brand")

            if brand and brand.lower() not in [t.lower() for t in terms]:
                terms.append(brand.lower())

            logger.info(
                f"[PS] query='{query}' | normalized='{query_normalized}' | "
                f"category={category} | terms={terms} | synonyms={synonyms}"
            )

            async with AsyncSessionFactory() as session:
                scored_map: dict[int, tuple[ProductModel, float]] = {}

                # Step 1: Category-first fetch
                if category:
                    for row in await self._fetch_by_category(session, category, limit * 3):
                        scored_map[row.id] = (row, _score_row(row, terms, query_normalized))

                # Step 2: Token OR search (English terms)
                if len(scored_map) < limit and terms:
                    for row in await self._fetch_by_terms(session, terms, limit * 3):
                        new_score = _score_row(row, terms, query_normalized)
                        if row.id not in scored_map or new_score > scored_map[row.id][1]:
                            scored_map[row.id] = (row, new_score)

                # Step 3: Synonym search (Arabic terms)
                if len(scored_map) < SEARCH_MIN_RESULTS and synonyms:
                    logger.debug(f"[PS] Trying synonym search with: {synonyms}")
                    for row in await self._fetch_by_synonyms(session, synonyms, limit * 3):
                        if row.id not in scored_map:
                            syn_score = _score_row(row, synonyms, query_normalized) * 0.8
                            scored_map[row.id] = (row, syn_score)

                # Step 4: Related terms broadening
                if len(scored_map) < SEARCH_MIN_RESULTS:
                    for row in await self._fetch_related(
                        session, terms, set(scored_map.keys()), limit * 2
                    ):
                        scored_map[row.id] = (row, _score_row(row, terms, query_normalized) * 0.6)

                # Step 5: Category fallback
                if len(scored_map) < 3 and scored_map:
                    first_cat = next(iter(scored_map.values()))[0].category
                    for row in await self._fetch_by_category(session, first_cat, limit):
                        if row.id not in scored_map:
                            scored_map[row.id] = (row, _score_row(row, terms, query_normalized) * 0.3)

                # Sort by score and prepare results
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

    async def by_category(self, category: str, limit: int = SEARCH_MAX_RESULTS) -> list[dict]:
        """Fetch products by category."""
        try:
            async with AsyncSessionFactory() as session:
                rows = await self._fetch_by_category(session, category, limit)
                return [_row_to_dict(r) for r in rows]
        except Exception:
            logger.error(f"[PS] Error in by_category '{category}'", exc_info=True)
            return []

    async def get_product_by_id(self, product_id: int) -> dict | None:
        """Fetch single product by ID."""
        try:
            async with AsyncSessionFactory() as session:
                row = await session.get(ProductModel, product_id)
                return _row_to_dict(row) if row else None
        except Exception:
            logger.error(f"[PS] Error fetching product {product_id}", exc_info=True)
            return None

    def all_categories(self) -> list[str]:
        """Return list of valid product categories."""
        return [
            "electronics",
            "jewelery",
            "men's clothing",
            "women's clothing",
            "beauty",
            "fragrances",
            "furniture",
            "groceries",
        ]


ProductService = _MySQLProductService