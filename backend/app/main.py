# app/main.py
"""متجر زكي AI Agent — FastAPI entry point.

Layered clean architecture:
  api (routers) → services → agents (LangGraph) → repositories → PostgreSQL+pgvector
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import close_db, init_db

settings = get_settings()
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_PARSED,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Customer routes ───────────────────────────────────────────────────────────
app.include_router(chat.router)
app.include_router(voice.router)
app.include_router(image.router)

# ── Admin CRUD routes ─────────────────────────────────────────────────────────
app.include_router(admin_products.router)
app.include_router(admin_stores.router)
app.include_router(admin_orders.router)
app.include_router(admin_sessions.router)

# ── WhatsApp / Twilio ─────────────────────────────────────────────────────────
app.include_router(whatsapp.router)
app.include_router(twilio_webhook.router)


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "customer_endpoints": {
            "POST /chat": "محادثة نصية",
            "POST /voice/chat": "محادثة صوتية",
            "POST /voice/transcribe": "تحويل صوت لنص",
            "POST /image/chat": "ابعت صورة منتج",
            "POST /image/analyze": "تحليل صورة بس",
        },
        "admin_endpoints": {
            "CRUD /admin/products": "إدارة المنتجات",
            "CRUD /admin/stores": "إدارة المتاجر",
            "CRUD /admin/orders": "إدارة الطلبات",
            "CRUD /admin/sessions": "إدارة المحادثات",
        },
        "whatsapp_endpoints": {
            "POST /twilio/webhook": "Webhook واتساب (Twilio)",
            "GET /whatsapp/status": "حالة خدمة واتساب",
        },
    }


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy"}