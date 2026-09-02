# app/api/routers/twilio_webhook.py
"""
Twilio webhook — receive inbound WhatsApp messages, reply with TwiML.

The flow: Twilio POSTs form fields (Body, From, WaId, ProfileName) here; we
route through the same ChatService as the web app and return TwiML so Twilio
sends the assistant's answer back to the customer's WhatsApp.
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_service
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.notifications.twilio_service import get_twilio_service

router = APIRouter(prefix="/twilio", tags=["Twilio Webhook"])
logger = get_logger(__name__)
settings = get_settings()


def _twiml(body: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>' f"<Response><Message>{body}</Message></Response>"


@router.post("/webhook")
async def twilio_webhook(
    request: Request,
    Body: str = Form(None),
    From: str = Form(None),
    WaId: str = Form(None),
    ProfileName: str = Form(None),
    db: AsyncSession = Depends(get_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    message = (Body or "").strip()
    sender_phone = (From or WaId or "").replace("whatsapp:", "").strip()
    logger.info("WhatsApp inbound from %s: %.80s", sender_phone, message)

    if not sender_phone:
        return Response(content=_twiml("خطأ في رقم المرسل"), media_type="application/xml")
    if not message:
        return Response(content="", media_type="application/xml")

    try:
        result = await chat_service.process(
            db,
            ChatRequest(
                message=message,
                session_id=f"whatsapp_{sender_phone}",
                customer_name=ProfileName,
                customer_phone=sender_phone,
            ),
        )
        return Response(content=_twiml(result.response), media_type="application/xml")
    except Exception as exc:
        logger.exception("Twilio webhook failed")
        return Response(
            content=_twiml("عذراً، حدث خطأ. حاول مرة أخرى."),
            media_type="application/xml",
        )


@router.get("/status")
async def twilio_status():
    twilio = get_twilio_service()
    return {
        "available": twilio.available,
        "whatsapp_number": settings.TWILIO_WHATSAPP_NUMBER,
        "configured": bool(
            settings.TWILIO_ACCOUNT_SID
            and settings.TWILIO_AUTH_TOKEN
            and settings.TWILIO_WHATSAPP_NUMBER
        ),
    }