# routes/meta_webhook.py
"""
Meta WhatsApp Cloud API Webhook.
GET  /meta/webhook  — التحقق من الـ webhook عند الإعداد
POST /meta/webhook  — استقبال الرسائل الواردة
"""
import json
import logging
from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import PlainTextResponse

from agents.text_assistant import TextAssistant
from agents.meta_service import get_meta_service, verify_meta_signature
from config.settings import get_settings
from middleware.rate_limiter import check_rate_limit

router   = APIRouter(prefix="/meta", tags=["Meta Webhook"])
logger   = logging.getLogger(__name__)
settings = get_settings()

_assistant = TextAssistant()

# ✅ FIX 2: سجل message IDs المعالجة عشان نمنع التكرار
_processed_message_ids: set[str] = set()
_MAX_PROCESSED_IDS = 1000  # بنمسح لما يوصل لـ 1000 عشان الـ memory ما تتملاش


# ── GET: Webhook Verification ─────────────────────────────────────────────────
@router.get("/webhook")
async def verify_webhook(
    hub_mode:         str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge:    str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("✅ Meta Webhook تم التحقق منه بنجاح")
        return PlainTextResponse(content=hub_challenge)

    logger.warning(f"⚠️  فشل التحقق من Webhook | token: {hub_verify_token}")
    raise HTTPException(status_code=403, detail="Forbidden — verify token غلط")


# ── POST: Incoming Messages ───────────────────────────────────────────────────
@router.post("/webhook")
async def receive_message(request: Request):
    global _processed_message_ids

    raw_body = await request.body()

    # ── 1. تحقق من الـ Signature ─────────────────────────────────────────────
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_meta_signature(raw_body, signature):
        logger.warning("⚠️  Webhook signature خاطئ — طلب مرفوض")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="JSON غير صالح")

    # ── 2. استخرج الرسالة ────────────────────────────────────────────────────
    try:
        entry    = data.get("entry", [{}])[0]
        change   = entry.get("changes", [{}])[0]
        value    = change.get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if not messages:
            return {"status": "ok"}

        msg          = messages[0]
        msg_id       = msg.get("id", "")
        msg_type     = msg.get("type", "")
        sender_phone = msg.get("from", "")
        profile_name = contacts[0].get("profile", {}).get("name", "") if contacts else ""

        # ✅ FIX 2: تجاهل الرسائل المكررة
        if msg_id and msg_id in _processed_message_ids:
            logger.info(f"⚠️  رسالة مكررة تم تجاهلها | ID: {msg_id}")
            return {"status": "ok"}

        # سجّل الـ message ID
        if msg_id:
            _processed_message_ids.add(msg_id)
            # امسح القديم لو وصل الحد
            if len(_processed_message_ids) > _MAX_PROCESSED_IDS:
                _processed_message_ids = set(list(_processed_message_ids)[-500:])

        # ── 3. Rate Limiting ─────────────────────────────────────────────────
        if not check_rate_limit(sender_phone):
            logger.warning(f"⚠️  Rate limit وصل الحد لـ {sender_phone}")
            meta = get_meta_service()
            await meta.send_message(
                sender_phone,
                "عذراً، أرسلت رسائل كتير. انتظر دقيقة واحدة ثم حاول مجدداً 🙏"
            )
            return {"status": "rate_limited"}

        # ── 4. نعالج النص فقط ────────────────────────────────────────────────
        if msg_type != "text":
            meta = get_meta_service()
            await meta.send_message(
                sender_phone,
                "أنا بفهم النص فقط حالياً 😊 اكتب سؤالك وأنا هساعدك!"
            )
            return {"status": "ok"}

        message_body = msg.get("text", {}).get("body", "").strip()
        if not message_body:
            return {"status": "ok"}

        print("=" * 55)
        print(f"📩 رسالة واردة")
        print(f"👤 من     : {sender_phone}")
        print(f"🙍 الاسم  : {profile_name or 'غير معروف'}")
        print(f"💬 الرسالة: {message_body}")
        print("=" * 55)

        # ── 5. معالجة الرسالة بالـ AI ────────────────────────────────────────
        result = await _assistant.process(
            message=message_body,
            session_id=f"wa_{sender_phone}",
            customer_name=profile_name,
            customer_phone=sender_phone,
        )

        response_text = result.get("response", "شكراً لتواصلك مع متجر زكي 🛍️")

        # ── 6. إرسال الرد ────────────────────────────────────────────────────
        meta = get_meta_service()
        send_result = await meta.send_message(sender_phone, response_text)

        print(f"📤 رد أُرسل → {sender_phone} | نجاح: {send_result.get('success')}")

        return {"status": "ok"}

    except Exception as exc:
        logger.error(f"❌ خطأ في معالجة الرسالة: {exc}", exc_info=True)
        return {"status": "error", "detail": str(exc)}


# ── GET: Status Check ─────────────────────────────────────────────────────────
@router.get("/status")
async def meta_status():
    meta = get_meta_service()
    return {
        "available":       meta.is_available(),
        "phone_number_id": settings.META_PHONE_NUMBER_ID or "غير مضبوط",
        "configured":      bool(settings.META_ACCESS_TOKEN and settings.META_PHONE_NUMBER_ID),
        "verify_token":    settings.META_VERIFY_TOKEN,
    }