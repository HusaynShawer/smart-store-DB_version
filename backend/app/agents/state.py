# app/agents/state.py
"""Type-safe LangGraph state shared by all agent nodes."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Request context
    input: str
    session_id: str | None
    customer_name: str | None
    customer_phone: str | None
    selected_product: dict | None
    location_text: str | None
    latitude: float | None
    longitude: float | None

    # Understanding / planning
    language: str
    intent: str
    chat_history: str
    vision_context: str | None

    # Working results
    products: list[dict]
    nearby_stores: list[dict]
    order_confirmation: dict | None

    # Output
    response: str
    answer_state: str
    error: str | None