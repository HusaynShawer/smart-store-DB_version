# app/api/routers/voice.py
"""Voice chat — multipart audio → Gemini STT → assistant."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_service, get_voice_service
from app.db.session import get_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_TYPES = {"audio/mpeg", "audio/mp4", "audio/m4a", "audio/wav", "audio/webm", "audio/ogg", "audio/x-m4a"}
ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg"}


def _validate_audio(file: UploadFile, content: bytes) -> None:
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="حجم الملف كبير جداً. الحد الأقصى 10 MB")
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"نوع الملف غير مدعوم: '{ext}'")
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Content type غير مدعوم: '{file.content_type}'")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="الملف فاضي")


def _parse_product(payload: str | None) -> dict | None:
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


@router.post("/chat", response_model=ChatResponse, summary="محادثة صوتية")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str | None = Form(None),
    customer_name: str | None = Form(None),
    customer_phone: str | None = Form(None),
    selected_product: str | None = Form(None),
    db: AsyncSession = Depends(get_session),
    chat_service: ChatService = Depends(get_chat_service),
    voice: VoiceService = Depends(get_voice_service),
):
    audio_bytes = await audio.read()
    _validate_audio(audio, audio_bytes)
    mime = audio.content_type or "audio/m4a"
    text = await voice.transcribe(audio_bytes, mime_type=mime)

    request = ChatRequest(
        message=text,
        session_id=session_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        selected_product=_parse_product(selected_product),
    )
    return await chat_service.process(db, request)


@router.post("/transcribe", summary="تحويل صوت لنص فقط")
async def transcribe(
    audio: UploadFile = File(...),
    voice: VoiceService = Depends(get_voice_service),
):
    audio_bytes = await audio.read()
    _validate_audio(audio, audio_bytes)
    mime = audio.content_type or "audio/m4a"
    return {"text": await voice.transcribe(audio_bytes, mime_type=mime)}