# app/services/order_service.py
"""OrderService — business rules for placing an order (single use case)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import OrderModel
from app.db.repositories.order import OrderRepository
from app.db.repositories.store import StoreRepository
from app.services.notifications.twilio_service import get_twilio_service

logger = get_logger(__name__)


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._orders = OrderRepository(session)
        self._stores = StoreRepository(session)

    async def create_order(
        self,
        customer_name: str,
        customer_phone: str,
        product_id: int | str,
        product_name: str,
        product_price: float,
        shop_id: int | None = None,
        product_url: str | None = None,
        vendor_phone: str | None = None,
    ) -> dict:
        """Persist the order and notify the vendor over WhatsApp (best effort)."""
        # Resolve vendor phone from store if it wasn't provided.
        if not vendor_phone and shop_id:
            store = await self._stores.get(int(shop_id))
            vendor_phone = store.phone if store else None

        order = await self._orders.add(
            OrderModel(
                customer_name=customer_name,
                customer_phone=customer_phone,
                product_id=str(product_id),
                product_name=product_name,
                product_price=product_price,
                shop_id=str(shop_id) if shop_id else None,
                product_url=product_url,
                vendor_phone=vendor_phone,
                status="pending",
            )
        )

        twilio_sent = False
        twilio_error = None
        if vendor_phone:
            twilio = get_twilio_service()
            result = twilio.send_vendor_notification(
                vendor_phone=vendor_phone,
                customer_name=customer_name,
                customer_phone=customer_phone,
                product_name=product_name,
                product_price=product_price,
                order_id=order.id,
            )
            twilio_sent = result.get("success", False)
            if not twilio_sent:
                twilio_error = result.get("error")
                logger.warning("Vendor WhatsApp notification failed: %s", twilio_error)

        return {
            "success": True,
            "order_id": order.id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "product_name": product_name,
            "product_price": product_price,
            "vendor_phone": vendor_phone,
            "twilio_sent": twilio_sent,
            "twilio_error": twilio_error,
        }

    def whatsapp_vendor_link(self, product_name: str, product_price: float, customer_name: str, customer_phone: str, vendor_phone: str | None) -> str | None:
        """Build a wa.me deep link so the customer can talk to the vendor."""
        if not vendor_phone:
            return None
        digits = "".join(ch for ch in vendor_phone if ch.isdigit())
        if digits.startswith("0"):
            digits = "2" + digits  # Egypt country code
        message = (
            f"مرحباً، لدي طلب من متجر زكي%0A%0A"
            f"المنتج: {product_name}%0Aالسعر: ${product_price}%0A"
            f"العميل: {customer_name}%0Aرقم العميل: {customer_phone}"
        )
        return f"https://wa.me/{digits}?text={message}"