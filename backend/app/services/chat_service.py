# app/services/chat_service.py
"""ChatService — one entry point for all conversational channels.

Each call:
  1. builds the LangGraph agent bound to the request DB session,
  2. wires the input/persona/location context into the initial AgentState,
  3. persists the user + assistant turns to the session history.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_graph
from app.agents.state import AgentState
from app.core.logging import get_logger
from app.db.repositories.session import SessionRepository
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.order import OrderConfirmation

logger = get_logger(__name__)


class ChatService:
    async def process(
        self, session: AsyncSession, request: ChatRequest
    ) -> ChatResponse:
        graph = build_graph(session)
        initial: AgentState = {
            "input": request.message,
            "session_id": request.session_id,
            "customer_name": request.customer_name,
            "customer_phone": request.customer_phone,
            "selected_product": request.selected_product,
            "location_text": request.location_text,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "answer_state": "conversation",
        }

        try:
            result = await graph.ainvoke(initial)
            response = result.get("response") or "عذراً، حصل خطأ غير متوقع 🙏"
            state = result.get("answer_state", "conversation")
        except Exception as exc:
            logger.exception("Agent failed")
            response = f"عذراً، حدث خطأ: {exc}"
            state = "error"
            result = {}

        await SessionRepository(session).append_messages(
            request.session_id,
            [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": response},
            ],
        ) if request.session_id else None

        return ChatResponse(
            response=response,
            state=state,
            products=result.get("products") or None,
            order_confirmation=self._confirmation(result.get("order_confirmation")),
            nearby_stores=result.get("nearby_stores") or None,
        )

    @staticmethod
    def _confirmation(data: dict | None) -> OrderConfirmation | None:
        if not data:
            return None
        return OrderConfirmation(
            order_id=data["order_id"],
            product_name=data["product_name"],
            product_price=data["product_price"],
            customer_name=data["customer_name"],
            customer_phone=data["customer_phone"],
            vendor_phone=data.get("vendor_phone"),
            twilio_sent=data.get("twilio_sent", False),
        )