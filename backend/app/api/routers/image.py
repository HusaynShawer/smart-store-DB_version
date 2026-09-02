# app/api/routers/image.py
"""Image chat — upload a product photo → Gemini vision → assistant."""
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_service, get_vision_service
from app.core.logging import get_logger
from app.db.session import get_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.vision_service import (
    ALLOWED_EXT,
    ALLOWED_TYPES,
    MAX_SIZE,
    VisionService,
)

router = APIRouter(prefix="/image", tags=["Image"])
logger = get_logger(__name__)


def _validate_image(file: UploadFile, content: bytes) -> None:
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="الصورة كبيرة جداً. الحد الأقصى 10 MB")
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=415, detail=f"نوع الصورة غير مدعوم: '{ext}'")
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


@router.post("/chat", response_model=ChatResponse, summary="ابعت صورة منتج والـ AI يدور عليه")
async def image_chat(
    image: UploadFile = File(...),
    session_id: str | None = Form(None),
    customer_name: str | None = Form(None),
    customer_phone: str | None = Form(None),
    selected_product: str | None = Form(None),
    message: str | None = Form(None),
    db: AsyncSession = Depends(get_session),
    chat_service: ChatService = Depends(get_chat_service),
    vision: VisionService = Depends(get_vision_service),
):
    image_bytes = await image.read()
    _validate_image(image, image_bytes)
    mime = image.content_type or "image/jpeg"
    try:
        detected = await vision.analyze(image_bytes, mime_type=mime)
    except Exception as exc:
        logger.warning("Vision analysis failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="تعذر تحليل الصورة. جرّب صورة أوضح بمنتج رئيسي واحد في الإضاءة الجيدة.",
        ) from exc

    message = (message or "").strip()
    vision_note = f"[Product image identified as: {detected}]"
    if message:
        query = f"{message}\n{vision_note}"
    else:
        # Use the clean vision-detected query as the search input; the marker
        # only provides follow-up context (vision_context) for the LLM.
        query = f"{detected}\n{vision_note}"

    request = ChatRequest(
        message=query,
        session_id=session_id,
        customer_name=customer_name,
        customer_phone=customer_phone,
        selected_product=_parse_product(selected_product),
    )
    return await chat_service.process(db, request)


@router.post("/analyze", summary="تحليل الصورة بس من غير بحث")
async def analyze_only(
    image: UploadFile = File(...),
    vision: VisionService = Depends(get_vision_service),
):
    image_bytes = await image.read()
    _validate_image(image, image_bytes)
    mime = image.content_type or "image/jpeg"
    return {"detected_product": await vision.analyze(image_bytes, mime_type=mime)}