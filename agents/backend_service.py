# agents/backend_service.py
"""
BackendService — يجيب المتاجر ويحفظ الطلبات في MySQL.
"""
import logging
from sqlalchemy import select, or_
from config.database import AsyncSessionFactory, StoreModel, OrderModel
from agents.meta_service import get_meta_service

logger = logging.getLogger(__name__)


def _store_to_dict(row: StoreModel) -> dict:
    return {
        "id":          str(row.id),
        "name":        row.name,
        "governorate": row.governorate,
        "lat":         row.lat,
        "lon":         row.lon,
        "phone":       row.phone,
        "products":    row.products,
    }


class BackendService:

    # ── Orders ────────────────────────────────────────────────────────────────

    async def send_order(
        self,
        customer_name:  str,
        customer_phone: str,
        product_id:     str,
        product_name:   str,
        product_price:  float,
        shop_id:        str  = None,
        product_url:    str  = None,
        vendor_phone:   str  = None,
    ) -> dict:
        try:
            async with AsyncSessionFactory() as session:
                # جيب بيانات المتجر لو عندنا shop_id
                shop_name = ""
                if shop_id:
                    stmt  = select(StoreModel).where(StoreModel.id == int(shop_id))
                    store = (await session.execute(stmt)).scalar_one_or_none()
                    if store:
                        vendor_phone = vendor_phone or store.phone
                        shop_name    = store.name

                order = OrderModel(
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    product_id=str(product_id),
                    product_name=product_name,
                    product_price=product_price,
                    shop_id=shop_id,
                    product_url=product_url,
                    vendor_phone=vendor_phone,
                    status="pending",
                )
                session.add(order)
                await session.commit()
                await session.refresh(order)

            # ── إرسال إشعار واتساب للتاجر ────────────────────────────────────
            meta        = get_meta_service()
            notify_sent = False
            notify_err  = None

            if vendor_phone and meta.is_available():
                result = await meta.send_vendor_notification(
                    vendor_phone=vendor_phone,
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    product_name=product_name,
                    product_price=product_price,
                    order_id=order.id,
                    shop_name=shop_name,
                )
                notify_sent = result.get("success", False)
                notify_err  = result.get("error")

                # ── إرسال تأكيد للعميل أيضاً ─────────────────────────────────
                if notify_sent and customer_phone:
                    await meta.send_customer_confirmation(
                        customer_phone=customer_phone,
                        product_name=product_name,
                        vendor_name=shop_name or "المتجر",
                        vendor_phone=vendor_phone,
                    )

            return {
                "success": True,
                "data": {
                    "order_id":       order.id,
                    "customer_name":  customer_name,
                    "product_name":   product_name,
                    "product_price":  product_price,
                    "vendor_phone":   vendor_phone,
                    "notify_sent":    notify_sent,
                    "notify_error":   notify_err,
                },
            }
        except Exception as exc:
            logger.error(f"❌ خطأ في حفظ الطلب: {exc}")
            return {"success": False, "error": str(exc)}

    # ── Stores ────────────────────────────────────────────────────────────────

    async def get_stores_by_product(self, product_query: str) -> list[dict]:
        """يجيب المتاجر التي تبيع منتجاً معيناً بالبحث في products_csv."""
        q = product_query.lower().strip()
        async with AsyncSessionFactory() as session:
            stmt   = select(StoreModel).where(
                StoreModel.is_active == True,
                StoreModel.products_csv.ilike(f"%{q}%"),
            )
            result = await session.execute(stmt)
            rows   = result.scalars().all()

            if not rows:
                # fallback: كل المتاجر النشطة
                all_stmt = select(StoreModel).where(StoreModel.is_active == True)
                rows     = (await session.execute(all_stmt)).scalars().all()

            return [_store_to_dict(r) for r in rows]

    async def get_stores_for_product(self, product: dict) -> list[dict]:
        """
        ✅ FIX: يجيب المتاجر الصح لكل منتج عن طريق مطابقة الكاتيجوري والعنوان.
        بدل match بالـ index الغلط.
        """
        category   = product.get("category", "").lower()
        title_word = product.get("title", "").split()[0].lower() if product.get("title") else ""

        search_terms = list({t for t in [category, title_word] if t})

        async with AsyncSessionFactory() as session:
            conditions = [
                StoreModel.products_csv.ilike(f"%{term}%")
                for term in search_terms
            ]
            stmt   = select(StoreModel).where(
                StoreModel.is_active == True,
                or_(*conditions),
            )
            result = await session.execute(stmt)
            rows   = result.scalars().all()

            if not rows:
                # fallback: كل المتاجر
                all_stmt = select(StoreModel).where(StoreModel.is_active == True)
                rows     = (await session.execute(all_stmt)).scalars().all()

            return [_store_to_dict(r) for r in rows]

    async def get_store_by_id(self, store_id: int) -> dict | None:
        async with AsyncSessionFactory() as session:
            row = await session.get(StoreModel, store_id)
            return _store_to_dict(row) if row else None

    async def get_all_orders(self, limit: int = 50) -> list[dict]:
        async with AsyncSessionFactory() as session:
            stmt   = select(OrderModel).order_by(OrderModel.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            rows   = result.scalars().all()
            return [
                {
                    "id":             r.id,
                    "customer_name":  r.customer_name,
                    "customer_phone": r.customer_phone,
                    "product_name":   r.product_name,
                    "product_price":  r.product_price,
                    "status":         r.status,
                    "vendor_phone":   r.vendor_phone,
                    "created_at":     str(r.created_at),
                }
                for r in rows
            ]