# routes/image.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import json

from models.schemas import ChatResponse
from agents.text_assistant import TextAssistant
from agents.vision_service import VisionService, ALLOWED_EXT, ALLOWED_TYPES, MAX_SIZE

router = APIRouter(prefix="/image", tags=["Image"])

_assistant = TextAssistant()
_vision    = VisionService()


def _validate_image(file: UploadFile, content: bytes):
    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"الصورة كبيرة جداً. الحد الأقصى {MAX_SIZE // (1024*1024)} MB"
        )
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=415,
            detail=f"نوع الصورة غير مدعوم: '{ext}'. المسموح: {', '.join(ALLOWED_EXT)}"
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="الملف فاضي")


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="ابعت صورة منتج والـ AI يدور عليه",
)
async def image_chat(
    image: UploadFile = File(..., description="صورة المنتج (jpg/png/webp)"),
    session_id:       Optional[str] = Form(None),
    customer_name:    Optional[str] = Form(None),
    customer_phone:   Optional[str] = Form(None),
    selected_product: Optional[str] = Form(None),
):
    try:
        image_bytes = await image.read()
        _validate_image(image, image_bytes)

        search_query = _vision.analyze(image_bytes, filename=image.filename or "image.jpg")

        product_dict = None
        if selected_product:
            try:
                product_dict = json.loads(selected_product)
            except Exception:
                product_dict = None

        result = await _assistant.process(
            message=search_query,
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze", summary="تحليل الصورة بس من غير بحث")
async def analyze_only(image: UploadFile = File(...)):
    try:
        image_bytes = await image.read()
        _validate_image(image, image_bytes)
        query = _vision.analyze(image_bytes, filename=image.filename or "image.jpg")
        return {"detected_product": query}
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc() 
        raise HTTPException(status_code=500, detail=str(exc))