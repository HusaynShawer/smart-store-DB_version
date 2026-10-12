# app/api/routers/__init__.py
"""Aggregates all API routers for the FastAPI app."""
from app.api.routers import (
    admin_orders,
    admin_products,
    admin_sessions,
    admin_stores,
    chat,
    image,
    twilio_webhook,
    voice,
    whatsapp,
)

__all__ = [
    "admin_orders",
    "admin_products",
    "admin_sessions",
    "admin_stores",
    "chat",
    "image",
    "twilio_webhook",
    "voice",
    "whatsapp",
]