# agents/product_service.py
"""
ProductService — بيبحث في MySQL عن طريق SQLAlchemy async.
"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionFactory, ProductModel

AR_TO_EN = {
    # ── ملابس ──────────────────────────────────────────────────────────────────
    "تيشرت": "shirt",        "تي شيرت": "shirt",       "قميص": "shirt",
    "جاكيت": "jacket",       "جاكت": "jacket",          "جاكيتة": "jacket",
    "ملابس": "clothing",     "هدوم": "clothing",        "لبس": "clothing",
    "بنطلون": "pants",       "جينز": "jeans",           "فستان": "dress",
    "بلوزة": "blouse",       "سويتر": "sweater",        "هودي": "hoodie",

    # ── شاشات ─────────────────────────────────────────────────────────────────
    "شاشة": "monitor",       "شاشه": "monitor",         "شاشات": "monitor",
    "شاشه كمبيوتر": "monitor","شاشة كمبيوتر": "monitor",
    "مونيتور": "monitor",    "منيتور": "monitor",

    # ── إلكترونيات ────────────────────────────────────────────────────────────
    "إلكترونيات": "electronics","الكترونيات": "electronics","الكترونيك": "electronics",

    # ── تخزين ─────────────────────────────────────────────────────────────────
    "هارد": "drive",         "هارد ديسك": "drive",      "هارد خارجي": "drive",
    "تخزين": "ssd",          "اس اس دي": "ssd",

    # ── مجوهرات ───────────────────────────────────────────────────────────────
    "مجوهرات": "jewelery",   "جواهر": "jewelery",
    "خاتم": "ring",          "دبلة": "ring",            "خواتم": "ring",
    "حلق": "earring",        "حلقان": "earring",
    "ذهب": "gold",           "فضة": "silver",
    "سلسلة": "necklace",     "سلسله": "necklace",       "عقد": "necklace",

    # ✅ تليفونات — أضفنا كل الكلمات الشائعة
    "تليفون": "phone",       "تلفون": "phone",          "هاتف": "phone",
    "موبايل": "phone",       "موبيل": "phone",          "جوال": "phone",
    "لابتوب": "laptop",      "كمبيوتر": "computer",     "حاسوب": "computer",
    "ايفون": "phone",        "آيفون": "phone",          "ايفون": "iphone",
    "سامسونج": "samsung",    "نوكيا": "nokia",          "شاومي": "xiaomi",
    "هواوي": "huawei",       "اوبو": "oppo",            "ريلمي": "realme",
    "ايباد": "tablet",       "تابلت": "tablet",

    # ── ألوان ─────────────────────────────────────────────────────────────────
    "أبيض": "white",         "ابيض": "white",
    "أسود": "black",         "اسود": "black",
    "أحمر": "red",           "ازرق": "blue",            "أزرق": "blue",

    # ── حقائب ─────────────────────────────────────────────────────────────────
    "حقيبة": "backpack",     "شنطة": "backpack",        "شنطه": "backpack",

    # ── ألعاب ─────────────────────────────────────────────────────────────────
    "العاب": "gaming",       "جيمينج": "gaming",        "جيمنج": "gaming",
    "سوني": "playstation",   "بلايستيشن": "playstation", "بلاي ستيشن": "playstation",
    "اكس بوكس": "xbox",

    # ── جمال وعناية ───────────────────────────────────────────────────────────
    "ماسكارا": "mascara",    "مكياج": "makeup",         "عطر": "perfume",
    "كريم": "cream",         "عناية": "skincare",

    # ── إنجليزي ───────────────────────────────────────────────────────────────
    "screen": "monitor",     "display": "monitor",      "mobile": "phone",
}

# ✅ Related terms to broaden search results
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
    q = query.lower().strip()
    for ar in sorted(AR_TO_EN.keys(), key=len, reverse=True):
        if ar in q:
            q = q.replace(ar, AR_TO_EN[ar])
    return q


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


class _MySQLProductService:

    async def _search_with_term(self, session: AsyncSession, term: str, limit: int) -> list:
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
        async with AsyncSessionFactory() as session:
            translated = _translate(query)

            # ✅ Primary search
            rows = await self._search_with_term(session, translated, limit)

            # ✅ Fallback: try original Arabic if translation gave no results
            if not rows and translated != query.lower().strip():
                rows = await self._search_with_term(session, query.strip(), limit)

            # ✅ Broadened search: if less than 5 results, search related terms
            if len(rows) < 5:
                seen_ids = {r.id for r in rows}
                related = RELATED_TERMS.get(translated.lower(), [])

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

            # ✅ Last resort: return products from same category
            if len(rows) < 5 and rows:
                category = rows[0].category
                seen_ids = {r.id for r in rows}
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

            return [_row_to_dict(r) for r in rows[:10]]

    async def by_category(self, category: str, limit: int = 10) -> list:
        async with AsyncSessionFactory() as session:
            stmt = (
                select(ProductModel)
                .where(ProductModel.category.ilike(f"%{category}%"))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return [_row_to_dict(r) for r in result.scalars().all()]

    async def get_product_by_id(self, product_id: int) -> dict:
        """Get a single product by ID"""
        async with AsyncSessionFactory() as session:
            stmt = select(ProductModel).where(ProductModel.id == product_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return _row_to_dict(row)
            return None

    def all_categories(self) -> list:
        return ["electronics", "jewelery", "men's clothing", "women's clothing",
                "beauty", "fragrances", "furniture", "groceries"]


ProductService = _MySQLProductService