# app/services/notifications/twilio_service.py
"""
Twilio WhatsApp notifications for vendors + customers.

Sends messages only when credentials are configured; degrades gracefully
(logs) otherwise so the API never fails because WhatsApp is offline.
"""
import re
from functools import lru_cache
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class TwilioService:
    def __init__(self) -> None:
        self._client: Client | None = None
        self._configured = False
        self._init_client()

    def _init_client(self) -> None:
        if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
            try:
                self._client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                self._configured = True
                logger.info("Twilio client initialized.")
            except Exception as exc:
                logger.error("Twilio init failed: %s", exc)
        else:
            logger.warning("Twilio credentials missing — WhatsApp notifications disabled.")

    @property
    def available(self) -> bool:
        return self._configured and self._client is not None

    def format_phone_number(self, phone: str) -> str:
        """Normalize an Egyptian number to E.164 (+20...) for Twilio."""
        if not phone:
            return ""
        cleaned = re.sub(r"\D", "", phone)
        if cleaned.startswith("0") and len(cleaned) == 11:
            cleaned = "20" + cleaned[1:]
        elif cleaned.startswith("20") and len(cleaned) == 12:
            pass
        elif not cleaned.startswith("20") and len(cleaned) == 10:
            cleaned = "20" + cleaned
        return f"+{cleaned}"

    def send_whatsapp_message(self, to_phone: str, message: str) -> dict:
        """Send one WhatsApp message; returns {success, ...}."""
        if not self.available:
            return {"success": False, "error": "Twilio not configured"}
        if not to_phone:
            return {"success": False, "error": "No recipient phone"}
        try:
            formatted_to = f"whatsapp:{self.format_phone_number(to_phone)}"
            formatted_from = f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}"
            msg = self._client.messages.create(
                body=message, from_=formatted_from, to=formatted_to
            )
            logger.info("WhatsApp sent to %s (SID=%s)", to_phone, msg.sid)
            return {
                "success": True,
                "message_sid": msg.sid,
                "status": msg.status,
                "to": to_phone,
            }
        except TwilioRestException as exc:
            logger.error("Twilio error (%s): %s", exc.code, exc.msg)
            return {"success": False, "error": exc.msg, "code": exc.code}
        except Exception as exc:
            logger.error("Twilio unexpected error: %s", exc)
            return {"success": False, "error": str(exc)}

    def send_vendor_notification(
        self,
        vendor_phone: str,
        customer_name: str,
        customer_phone: str,
        product_name: str,
        product_price: float,
        order_id: int,
    ) -> dict:
        message = (
            "طلب جديد من متجر زكي\n───────────────────\n"
            f"المنتج: {product_name}\nالسعر: ${product_price}\n"
            f"العميل: {customer_name}\nرقم العميل: {customer_phone}\n"
            f"رقم الطلب: #{order_id}\n───────────────────\n"
            "يرجى التواصل مع العميل لتأكيد الطلب 🙏"
        )
        return self.send_whatsapp_message(vendor_phone, message)


@lru_cache(maxsize=1)
def get_twilio_service() -> TwilioService:
    return TwilioService()