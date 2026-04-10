# routes/chat.py
import logging
from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from agents.text_assistant import TextAssistant

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])
_assistant = TextAssistant()


@router.post("", response_model=ChatResponse, summary="Chat with shopping assistant")
async def chat(body: ChatRequest):
    """
    Process user message and return shopping assistant response with products.
    
    Supports:
    - Product search
    - Location-based recommendations
    - Order history
    - Purchase confirmation
    """
    try:
        logger.info(f"Processing chat request: {body.message[:50]}...")
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
        logger.info(f"Chat processed successfully. State: {result['state']}")
        return ChatResponse(
            response=result["response"],
            state=result["state"],
            products=result.get("products"),
            order_confirmation=result.get("order_confirmation"),
            nearby_stores=result.get("nearby_stores"),
        )
    except Exception as exc:
        logger.error(f"Error processing chat request", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error processing chat")