# routes/chat.py
from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from agents.text_assistant import TextAssistant

router = APIRouter(prefix="/chat", tags=["Chat"])
_assistant = TextAssistant()


@router.post("", response_model=ChatResponse, summary="دردش مع المساعد الذكي")
async def chat(body: ChatRequest):
    try:
        result = await _assistant.process(
            message=body.message,
            session_id=body.session_id,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            selected_product=body.selected_product,
            location_text=body.location_text,
            latitude=body.latitude,
            longitude=body.longitude,
        )
        return ChatResponse(
            response=result["response"],
            state=result["state"],
            products=result.get("products"),
            order_confirmation=result.get("order_confirmation"),
            nearby_stores=result.get("nearby_stores"),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))