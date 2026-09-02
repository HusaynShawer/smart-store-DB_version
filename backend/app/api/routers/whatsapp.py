# app/api/routers/whatsapp.py
"""WhatsApp helpers for vendors (wa.me deep links + status)."""
from fastapi import APIRouter, Query

from app.services.notifications.twilio_service import get_twilio_service

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


@router.get("/test", summary="Test router")
async def test():
    return {
        "success": True,
        "message": "WhatsApp router is working!",
        "endpoints": [
            "GET /whatsapp/test",
            "GET /whatsapp/vendor-link/{vendor_phone}",
            "POST /twilio/webhook",
            "GET /twilio/status",
        ],
    }


@router.get("/vendor-link/{vendor_phone}", summary="WhatsApp deep link for a vendor")
async def vendor_link(
    vendor_phone: str,
    message: str = Query(
        default="مرحباً، لدي طلب من متجر زكي%0Aالمنتج: ...%0Aالسعر: ...",
        description="URL-encoded message",
    ),
):
    digits = "".join(ch for ch in vendor_phone if ch.isdigit())
    if digits.startswith("0"):
        digits = "2" + digits
    return {"vendor_phone": vendor_phone, "link": f"https://wa.me/{digits}?text={message}"}


@router.get("/status", summary="Twilio service status")
async def twilio_status():
    twilio = get_twilio_service()
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "available": twilio.available,
        "whatsapp_number": settings.TWILIO_WHATSAPP_NUMBER,
        "configured": bool(settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN),
    }