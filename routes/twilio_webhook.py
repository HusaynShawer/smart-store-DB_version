# routes/twilio_webhook.py
"""
Twilio Webhook endpoints to receive incoming WhatsApp messages.
"""
from fastapi import APIRouter, Request, Form
from fastapi.responses import Response
from typing import Optional
import logging

from agents.text_assistant import TextAssistant
from agents.twilio_service import get_twilio_service
from config.settings import get_settings

router = APIRouter(prefix="/twilio", tags=["Twilio Webhook"])
logger = logging.getLogger(__name__)
settings = get_settings()

_assistant = TextAssistant()
_twilio = get_twilio_service()


@router.post("/webhook")
async def twilio_webhook(
    request: Request,
    Body: str = Form(None),
    From: str = Form(None),
    WaId: str = Form(None),
    ProfileName: str = Form(None),
):
    """
    Receive incoming WhatsApp messages from Twilio.

    This endpoint is called by Twilio when a user sends a WhatsApp message.
    """
    try:
        message = Body or ""

        # Strip whatsapp: prefix that Twilio adds to the From field
        sender_phone = (From or WaId or "").replace("whatsapp:", "").strip()

        print("=" * 50)
        print(f"📩 Incoming WhatsApp message")
        print(f"👤 From       : {sender_phone}")
        print(f"🙍 Name       : {ProfileName or 'Unknown'}")
        print(f"💬 Message    : {message}")
        print("=" * 50)

        logger.info(f"📩 Received WhatsApp from {sender_phone}: {message}")

        if not message:
            return Response(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                media_type="application/xml"
            )

        # Process message through your assistant
        result = await _assistant.process(
            message=message,
            session_id=f"whatsapp_{sender_phone}",
            customer_name=ProfileName,
            customer_phone=sender_phone,
        )

        response_message = result.get("response", "شكراً لتواصلك مع متجر زكي 🛍️")

        print("=" * 50)
        print(f"📤 Sending reply to : {sender_phone}")
        print(f"💬 Reply            : {response_message[:100]}...")
        print("=" * 50)

        twiml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f"<Response><Message>{response_message}</Message></Response>"
        )

        # Return proper XML so Twilio sends the reply
        return Response(content=twiml_response, media_type="application/xml")

    except Exception as exc:
        logger.error(f"❌ Error processing Twilio webhook: {exc}", exc_info=True)
        print(f"❌ Webhook error: {exc}")

        # Return valid TwiML so Twilio doesn't retry endlessly
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response><Message>عذراً، حدث خطأ. حاول مرة أخرى.</Message></Response>',
            media_type="application/xml"
        )


@router.get("/status")
async def twilio_status():
    """Check Twilio service status."""
    twilio = get_twilio_service()

    status = {
        "available": twilio.is_available(),
        "whatsapp_number": settings.TWILIO_WHATSAPP_NUMBER,
        "configured": bool(
            settings.TWILIO_ACCOUNT_SID and
            settings.TWILIO_AUTH_TOKEN and
            settings.TWILIO_WHATSAPP_NUMBER
        )
    }

    print("=" * 50)
    print(f"🔍 Twilio Status Check")
    print(f"✅ Available  : {status['available']}")
    print(f"📱 Number     : {status['whatsapp_number']}")
    print(f"⚙️  Configured : {status['configured']}")
    print("=" * 50)

    return status