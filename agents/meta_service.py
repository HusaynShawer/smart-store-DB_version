# agents/meta_service.py
"""
MetaService — بيبعت رسائل WhatsApp عن طريق Meta Cloud API.
Features:
  - إرسال رسائل نصية
  - Retry تلقائي (3 محاولات)
  - حفظ الرسائل الفاشلة في DB
  - تنسيق أرقام مصرية
"""
import asyncio
import hashlib
import hmac
import logging
import re
from typing import Optional

import httpx

from config.settings import get_settings
from config.database import AsyncSessionFactory, FailedMessageModel

settings = get_settings()
logger   = logging.getLogger(__name__)

META_API_URL = "https://graph.facebook.com/v19.0"


def format_phone_eg(phone: str) -> str:
    """
    يحول أي رقم مصري لـ format مناسب لـ Meta API.
    01001111222 → 201001111222  (بدون + لأن Meta بتاخد الرقم كما هو)
    """
    if not phone:
        return ""
    cleaned = re.sub(r"\D", "", phone)
    if cleaned.startswith("0") and len(cleaned) == 11:
        cleaned = "2" + cleaned[1:]
    elif not cleaned.startswith("2") and len(cleaned) == 10:
        cleaned = "20" + cleaned
    return cleaned


def verify_meta_signature(payload: bytes, signature_header: str) -> bool:
    """
    يتحقق من صحة الـ Webhook request جاي من Meta فعلاً.
    يستخدم HMAC-SHA256 مع APP_SECRET.
    """
    if not settings.META_APP_SECRET:
        logger.warning(" META_APP_SECRET غير مضبوط — تجاوز التحقق")
        return True

    expected = "sha256=" + hmac.new(
        settings.META_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header or "")


class MetaService:

    def __init__(self):
        self._ok = bool(settings.META_ACCESS_TOKEN and settings.META_PHONE_NUMBER_ID)
        if self._ok:
            logger.info(" Meta WhatsApp Service جاهز")
        else:
            logger.warning("  META_ACCESS_TOKEN أو META_PHONE_NUMBER_ID غير مضبوطين")

    def is_available(self) -> bool:
        return self._ok

    async def send_message(
        self,
        to_phone: str,
        message:  str,
    ) -> dict:
        """يبعت رسالة مع retry تلقائي لو فشلت."""
        if not self.is_available():
            return {"success": False, "error": "Meta service غير مضبوط"}
        if not to_phone:
            return {"success": False, "error": "رقم المستلم فاضي"}

        formatted = format_phone_eg(to_phone)
        payload   = {
            "messaging_product": "whatsapp",
            "to":                formatted,
            "type":              "text",
            "text":              {"body": message},
        }
        headers = {
            "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
            "Content-Type":  "application/json",
        }
        url = f"{META_API_URL}/{settings.META_PHONE_NUMBER_ID}/messages"

        last_error = ""
        for attempt in range(1, settings.MESSAGE_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code == 200:
                    data = resp.json()
                    msg_id = data.get("messages", [{}])[0].get("id", "")
                    logger.info(f" رسالة أُرسلت → {to_phone} | ID: {msg_id}")
                    return {"success": True, "message_id": msg_id, "to": to_phone}

                last_error = f"HTTP {resp.status_code}: {resp.text}"
                logger.warning(f"  محاولة {attempt}/{settings.MESSAGE_MAX_RETRIES} فشلت: {last_error}")

            except httpx.RequestError as exc:
                last_error = str(exc)
                logger.warning(f"  محاولة {attempt} — خطأ شبكة: {exc}")

            if attempt < settings.MESSAGE_MAX_RETRIES:
                await asyncio.sleep(settings.MESSAGE_RETRY_DELAY * attempt)

        # ── كل المحاولات فشلت — حفظ في DB للمراجعة ──────────────────────────
        await self._save_failed(to_phone, message, last_error)
        return {"success": False, "error": last_error, "to": to_phone}

    async def _save_failed(self, to_phone: str, message: str, error: str):
        try:
            async with AsyncSessionFactory() as db:
                row = FailedMessageModel(
                    to_phone=to_phone,
                    message_body=message,
                    retries=settings.MESSAGE_MAX_RETRIES,
                    last_error=error,
                )
                db.add(row)
                await db.commit()
                logger.info(f" رسالة فاشلة اتحفظت في DB لـ {to_phone}")
        except Exception as exc:
            logger.error(f" مش قادر يحفظ الرسالة الفاشلة: {exc}")

    async def retry_failed_messages(self) -> dict:
        """يحاول يعيد إرسال الرسائل الفاشلة — يتنادى من background task."""
        from sqlalchemy import select
        retried, succeeded = 0, 0
        async with AsyncSessionFactory() as db:
            stmt   = select(FailedMessageModel).where(
                FailedMessageModel.is_resolved == False,
                FailedMessageModel.retries < 10,
            )
            result = await db.execute(stmt)
            rows   = result.scalars().all()

            for row in rows:
                retried += 1
                res = await self.send_message(row.to_phone, row.message_body)
                if res["success"]:
                    row.is_resolved = True
                    succeeded += 1
                else:
                    row.retries   += 1
                    row.last_error = res.get("error", "")
            await db.commit()

        return {"retried": retried, "succeeded": succeeded}

    async def send_vendor_notification(
        self,
        vendor_phone:   str,
        customer_name:  str,
        customer_phone: str,
        product_name:   str,
        product_price:  float,
        order_id:       int,
        shop_name:      str = "",
    ) -> dict:
        message = (
            f" *طلب جديد — متجر زكي*\n"
            f"─────────────────────\n"
            f" المنتج  : {product_name}\n"
            f" السعر   : {product_price} جنيه\n"
            f" العميل  : {customer_name}\n"
            f" تليفون  : {customer_phone}\n"
            f" رقم الطلب: #{order_id}\n"
            f"─────────────────────\n"
            f"يرجى التواصل مع العميل لتأكيد الطلب "
        )
        return await self.send_message(vendor_phone, message)

    async def send_customer_confirmation(
        self,
        customer_phone: str,
        product_name:   str,
        vendor_name:    str,
        vendor_phone:   str,
    ) -> dict:
        display = "0" + vendor_phone[2:] if vendor_phone.startswith("20") else vendor_phone
        message = (
            f" *تم إرسال طلبك بنجاح!*\n"
            f"─────────────────────\n"
            f" {product_name}\n"
            f"المتجر : {vendor_name}\n"
            f" التاجر سيتواصل معك على رقمك قريباً \n"
            f"─────────────────────\n"
            f"شكراً لتسوقك مع متجر زكي 💚"
        )
        return await self.send_message(customer_phone, message)


# ── Singleton ─────────────────────────────────────────────────────────────────
_meta_service: Optional[MetaService] = None


def get_meta_service() -> MetaService:
    global _meta_service
    if _meta_service is None:
        _meta_service = MetaService()
    return _meta_service