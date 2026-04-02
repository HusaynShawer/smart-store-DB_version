# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.database import create_all_tables, close_db

from routes.chat     import router as chat_router
from routes.voice    import router as voice_router
from routes.image    import router as image_router
from routes.products import router as products_router
from routes.stores   import router as stores_router
from routes.orders   import router as orders_router
from routes.sessions import router as sessions_router
from routes.whatsapp import router as whatsapp_router  # Add this
from routes.twilio_webhook import router as twilio_webhook_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.APP_TITLE} is running...")
    await create_all_tables()   # creates tables if they don't exist
    yield
    await close_db()
    print("🛑 Shutting down...")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Customer routes ───────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(image_router)

# ── Admin CRUD routes ─────────────────────────────────────────────────────────
app.include_router(products_router)
app.include_router(stores_router)
app.include_router(orders_router)
app.include_router(sessions_router)
app.include_router(whatsapp_router)  # Add this
app.include_router(twilio_webhook_router)  # Add this

@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "customer_endpoints": {
            "POST /chat":             "محادثة نصية",
            "POST /voice/chat":       "محادثة صوتية",
            "POST /voice/transcribe": "تحويل صوت لنص",
            "POST /image/chat":       "ابعت صورة منتج",
            "POST /image/analyze":    "تحليل صورة بس",
        },
        "admin_endpoints": {
            "CRUD /admin/products": "إدارة المنتجات",
            "CRUD /admin/stores":   "إدارة المتاجر",
            "CRUD /admin/orders":   "إدارة الطلبات",
            "CRUD /admin/sessions": "إدارة المحادثات",
        },
        "whatsapp_endpoints": {
            "POST /whatsapp/notify-vendor/{order_id}": "إرسال إشعار واتساب للتاجر",
            "GET  /whatsapp/vendor-link/{vendor_phone}": "رابط واتساب للتاجر",
        },
    }


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy"}