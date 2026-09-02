# app/schemas/chat.py
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.order import OrderConfirmation
from app.schemas.product import ProductOut
from app.schemas.store import StoreOut

AgentState = Literal[
    "searching",
    "product_found",
    "awaiting_confirm",
    "order_sent",
    "nearby",
    "conversation",
    "error",
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    selected_product: dict | None = None
    location_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ChatResponse(BaseModel):
    response: str
    state: AgentState = "conversation"
    products: list[ProductOut] | None = None
    order_confirmation: OrderConfirmation | None = None
    nearby_stores: list[StoreOut] | None = None