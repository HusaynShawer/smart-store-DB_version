# agents/backend_service.py (updated)
"""
BackendService — يجيب المتاجر ويحفظ الطلبات في MySQL.
"""
from datetime import datetime, timezone
from sqlalchemy import select, or_
from config.database import AsyncSessionFactory, StoreModel, OrderModel
from agents.twilio_service import get_twilio_service
import logging

logger = logging.getLogger(__name__)


async def close_client():
    """Kept for compatibility with main.py lifespan."""
    pass


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
        customer_name: str,
        customer_phone: str,
        product_id: str,
        product_name: str,
        product_price: float,
        shop_id: str = None,
        product_url: str = None,
        vendor_phone: str = None,
    ) -> dict:
        try:
            async with AsyncSessionFactory() as session:
                # Get shop info for WhatsApp message
                shop_info = None
                shop_name = None
                if shop_id:
                    stmt = select(StoreModel).where(StoreModel.id == int(shop_id))
                    result = await session.execute(stmt)
                    shop_info = result.scalar_one_or_none()
                    if shop_info:
                        vendor_phone = shop_info.phone
                        shop_name = shop_info.name
                
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
                
                # ── Send Twilio WhatsApp notification to vendor ─────────────────
                twilio_sent = False
                twilio_error = None
                
                if vendor_phone:
                    twilio = get_twilio_service()
                    if twilio.is_available():
                        result = twilio.send_vendor_notification(
                            vendor_phone=vendor_phone,
                            customer_name=customer_name,
                            customer_phone=customer_phone,
                            product_name=product_name,
                            product_price=product_price,
                            order_id=order.id
                        )
                        twilio_sent = result.get("success", False)
                        if not twilio_sent:
                            twilio_error = result.get("error")
                            logger.warning(f"Twilio notification failed: {twilio_error}")
                    else:
                        logger.warning("Twilio not available, skipping vendor notification")
                
                return {
                    "success": True,
                    "data": {
                        "message":       "تم استلام طلبك بنجاح ",
                        "order_id":      order.id,
                        "customer_name": customer_name,
                        "product_name":  product_name,
                        "product_price": product_price,
                        "vendor_phone":  vendor_phone,
                        "twilio_sent":   twilio_sent,
                        "twilio_error":  twilio_error,
                    },
                }
        except Exception as exc:
            logger.error(f"Error sending order: {exc}")
            return {"success": False, "error": str(exc)}

    # ── Stores ────────────────────────────────────────────────────────────────

    async def get_stores_by_product(self, product_query: str) -> list[dict]:
        q = product_query.lower().strip()
        async with AsyncSessionFactory() as session:
            # Search inside the comma-separated products_csv column
            stmt = select(StoreModel).where(
                StoreModel.products_csv.ilike(f"%{q}%")
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            # Fallback: return all stores if nothing matched
            if not rows:
                all_stmt = select(StoreModel)
                all_result = await session.execute(all_stmt)
                rows = all_result.scalars().all()

            return [_store_to_dict(r) for r in rows]
    
    async def get_store_by_id(self, store_id: int) -> dict:
        """Get store by ID"""
        async with AsyncSessionFactory() as session:
            stmt = select(StoreModel).where(StoreModel.id == store_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return _store_to_dict(row)
            return None