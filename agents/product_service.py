# agents/product_service.py
"""
ProductService for searching products in MySQL database using async SQLAlchemy.
"""
import logging
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionFactory, ProductModel

logger = logging.getLogger(__name__)

# Arabic to English translation mapping for product searches
AR_TO_EN = {
    # Clothing
    "تيشرت": "shirt",        "تي شيرت": "shirt",       "قميص": "shirt",
    "جاكيت": "jacket",       "جاكت": "jacket",          "جاكيتة": "jacket",
    "ملابس": "clothing",     "هدوم": "clothing",        "لبس": "clothing",
    "بنطلون": "pants",       "جينز": "jeans",           "فستان": "dress",
    "بلوزة": "blouse",       "سويتر": "sweater",        "هودي": "hoodie",

    # Monitors and Displays
    "شاشة": "monitor",       "شاشه": "monitor",         "شاشات": "monitor",
    "شاشه كمبيوتر": "monitor","شاشة كمبيوتر": "monitor",
    "مونيتور": "monitor",    "منيتور": "monitor",

    # Electronics
    "إلكترونيات": "electronics","الكترونيات": "electronics","الكترونيك": "electronics",

    # Storage
    "هارد": "drive",         "هارد ديسك": "drive",      "هارد خارجي": "drive",
    "تخزين": "ssd",          "اس اس دي": "ssd",

    # Jewelry
    "مجوهرات": "jewelery",   "جواهر": "jewelery",
    "خاتم": "ring",          "دبلة": "ring",            "خواتم": "ring",
    "حلق": "earring",        "حلقان": "earring",
    "ذهب": "gold",           "فضة": "silver",
    "سلسلة": "necklace",     "سلسله": "necklace",       "عقد": "necklace",

    # Phones and Computers
    "تليفون": "phone",       "تلفون": "phone",          "هاتف": "phone",
    "موبايل": "phone",       "موبيل": "phone",          "جوال": "phone",
    "لابتوب": "laptop",      "كمبيوتر": "computer",     "حاسوب": "computer",
    "ايفون": "phone",        "آيفون": "phone",          "ايفون": "iphone",
    "سامسونج": "samsung",    "نوكيا": "nokia",          "شاومي": "xiaomi",
    "هواوي": "huawei",       "اوبو": "oppo",            "ريلمي": "realme",
    "ايباد": "tablet",       "تابلت": "tablet",

    # Colors
    "أبيض": "white",         "ابيض": "white",
    "أسود": "black",         "اسود": "black",
    "أحمر": "red",           "ازرق": "blue",            "أزرق": "blue",

    # Bags
    "حقيبة": "backpack",     "شنطة": "backpack",        "شنطه": "backpack",

    # Gaming
    "العاب": "gaming",       "جيمينج": "gaming",        "جيمنج": "gaming",
    "سوني": "playstation",   "بلايستيشن": "playstation", "بلاي ستيشن": "playstation",
    "اكس بوكس": "xbox",

    # Beauty and Care
    "ماسكارا": "mascara",    "مكياج": "makeup",         "عطر": "perfume",
    "كريم": "cream",         "عناية": "skincare",

    # English terms
    "screen": "monitor",     "display": "monitor",      "mobile": "phone",
}

# Related terms mapping to broaden search results
RELATED_TERMS = {
    "ring":       ["ring", "jewelry", "jewelery", "gold", "necklace", "bracelet"],
    "phone":      ["phone", "mobile", "iphone", "samsung", "smartphone"],
    "laptop":     ["laptop", "computer", "notebook", "pc"],
    "shirt":      ["shirt", "clothing", "tshirt", "jacket", "men's clothing"],
    "jacket":     ["jacket", "shirt", "clothing", "men's clothing"],
    "jewelry":    ["jewelry", "jewelery", "ring", "gold", "necklace", "earring"],
    "jewelery":   ["jewelery", "jewelry", "ring", "gold", "necklace", "earring"],
    "gold":       ["gold", "ring", "jewelry", "jewelery", "necklace"],
    "earring":    ["earring", "jewelry", "jewelery", "ring", "gold"],
    "necklace":   ["necklace", "jewelry", "jewelery", "gold", "ring"],
    "monitor":    ["monitor", "screen", "display", "electronics"],
    "electronics":["electronics", "phone", "laptop", "monitor", "tablet"],
}


def _translate(query: str) -> str:
    """Translate Arabic search terms to English equivalents."""
    q = query.lower().strip()
    for ar in sorted(AR_TO_EN.keys(), key=len, reverse=True):
        if ar in q:
            q = q.replace(ar, AR_TO_EN[ar])
    return q


def _row_to_dict(row: ProductModel) -> dict:
    """Convert database ProductModel row to dictionary."""
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


class _MySQLProductService:
    """Service for searching and retrieving products from MySQL database."""

    async def _search_with_term(self, session: AsyncSession, term: str, limit: int) -> list:
        """Search products by a single term in title, description, or category."""
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
        result = await session.execute(stmt)
        return result.scalars().all()

    async def search(self, query: str, limit: int = 10) -> list:
        """
        Search for products with multiple fallback strategies.
        
        Strategy:
        1. Translate Arabic terms to English and search
        2. Fallback to original Arabic if no results
        3. Search related terms if less than 5 results
        4. Last resort: search same category as first result
        """
        try:
            async with AsyncSessionFactory() as session:
                translated = _translate(query)
                logger.info(f"Searching for: {query} (translated: {translated})")

                # Primary search
                rows = await self._search_with_term(session, translated, limit)

                # Fallback: try original Arabic if translation gave no results
                if not rows and translated != query.lower().strip():
                    logger.debug(f"Retrying with original Arabic term: {query}")
                    rows = await self._search_with_term(session, query.strip(), limit)

                # Broadened search: if less than 5 results, search related terms
                if len(rows) < 5:
                    seen_ids = {r.id for r in rows}
                    related = RELATED_TERMS.get(translated.lower(), [])
                    logger.debug(f"Searching related terms: {related}")

                    for term in related:
                        if len(rows) >= 10:
                            break
                        extra = await self._search_with_term(session, term, limit)
                        for r in extra:
                            if r.id not in seen_ids:
                                rows.append(r)
                                seen_ids.add(r.id)
                            if len(rows) >= 10:
                                break

                # Last resort: return products from same category
                if len(rows) < 5 and rows:
                    category = rows[0].category
                    seen_ids = {r.id for r in rows}
                    logger.debug(f"Searching category fallback: {category}")
                    cat_stmt = (
                        select(ProductModel)
                        .where(ProductModel.category.ilike(f"%{category}%"))
                        .limit(limit)
                    )
                    cat_result = await session.execute(cat_stmt)
                    for r in cat_result.scalars().all():
                        if r.id not in seen_ids:
                            rows.append(r)
                            seen_ids.add(r.id)
                        if len(rows) >= 10:
                            break

                result = [_row_to_dict(r) for r in rows[:10]]
                logger.info(f"Found {len(result)} products for query: {query}")
                return result
                
        except Exception as e:
            logger.error(f"Error searching for products: {query}", exc_info=True)
            return []

    async def by_category(self, category: str, limit: int = 10) -> list:
        """Get products filtered by category."""
        try:
            async with AsyncSessionFactory() as session:
                stmt = (
                    select(ProductModel)
                    .where(ProductModel.category.ilike(f"%{category}%"))
                    .limit(limit)
                )
                result = await session.execute(stmt)
                products = [_row_to_dict(r) for r in result.scalars().all()]
                logger.info(f"Retrieved {len(products)} products from category: {category}")
                return products
        except Exception as e:
            logger.error(f"Error retrieving products by category: {category}", exc_info=True)
            return []

    async def get_product_by_id(self, product_id: int) -> dict:
        """Get a single product by ID."""
        try:
            async with AsyncSessionFactory() as session:
                stmt = select(ProductModel).where(ProductModel.id == product_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row:
                    logger.debug(f"Retrieved product: {product_id}")
                    return _row_to_dict(row)
                logger.warning(f"Product not found: {product_id}")
                return None
        except Exception as e:
            logger.error(f"Error retrieving product by ID: {product_id}", exc_info=True)
            return None

    def all_categories(self) -> list:
        """Get list of all available product categories."""
        return ["electronics", "jewelery", "men's clothing", "women's clothing",
                "beauty", "fragrances", "furniture", "groceries"]


ProductService = _MySQLProductService