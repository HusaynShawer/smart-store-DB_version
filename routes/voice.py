# routes/voice.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json

from models.schemas import ChatResponse
from agents.text_assistant import TextAssistant
from agents.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])

_assistant = TextAssistant()
_voice     = VoiceService()

MAX_FILE_SIZE    = 10 * 1024 * 1024
ALLOWED_TYPES    = {
    "audio/mpeg", "audio/mp4", "audio/m4a", "audio/wav",
    "audio/webm", "audio/ogg", "audio/x-m4a",
}
ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg"}


def _validate_audio(file: UploadFile, content: bytes):
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الملف كبير جداً. الحد الأقصى {MAX_FILE_SIZE // (1024*1024)} MB"
        )
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"نوع الملف غير مدعوم: '{ext}'. الأنواع المسموحة: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Content type غير مدعوم: '{content_type}'")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="الملف فاضي")


@router.post("/chat", response_model=ChatResponse, summary="محادثة صوتية")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id:       Optional[str] = Form(None),
    customer_name:    Optional[str] = Form(None),
    customer_phone:   Optional[str] = Form(None),
    selected_product: Optional[str] = Form(None),
):
    try:
        audio_bytes = await audio.read()
        _validate_audio(audio, audio_bytes)

        text_input = _voice.speech_to_text(audio_bytes, filename=audio.filename or "audio.m4a")
        print(f"[VoiceChat] Transcribed: '{text_input}'")

        product_dict = None
        if selected_product:
            try:
                product_dict = json.loads(selected_product)
            except Exception:
                product_dict = None

        result = await _assistant.process(
            message=text_input,
            session_id=session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            selected_product=product_dict,
        )

        return ChatResponse(
            response=result["response"],
            state=result["state"],
            products=result.get("products"),
            order_confirmation=result.get("order_confirmation"),
        )

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/transcribe", summary="تحويل صوت لنص فقط")
async def transcribe(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        _validate_audio(audio, audio_bytes)
        text = _voice.speech_to_text(audio_bytes, filename=audio.filename or "audio.m4a")
        return {"text": text}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))