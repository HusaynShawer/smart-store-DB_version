# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from config.database import create_all_tables, close_db

from routes.chat          import router as chat_router
from routes.voice         import router as voice_router
from routes.image         import router as image_router
from routes.products      import router as products_router
from routes.stores        import router as stores_router
from routes.orders        import router as orders_router
from routes.sessions      import router as sessions_router
from routes.whatsapp      import router as whatsapp_router
from routes.meta_webhook  import router as meta_webhook_router
from routes.analytics     import router as analytics_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f" {settings.APP_TITLE} v{settings.APP_VERSION} يعمل...")
    await create_all_tables()
    yield
    await close_db()
    print(" إيقاف التشغيل...")


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

# ── Customer routes ──────────────────────────────────────────────────────────
app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(image_router)

# ── Admin CRUD routes ────────────────────────────────────────────────────────
app.include_router(products_router)
app.include_router(stores_router)
app.include_router(orders_router)
app.include_router(sessions_router)
app.include_router(analytics_router)

# ── WhatsApp / Meta ──────────────────────────────────────────────────────────
app.include_router(whatsapp_router)
app.include_router(meta_webhook_router)


@app.get("/", tags=["System"])
async def root():
    return {
        "name":    settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "whatsapp": "Meta WhatsApp Cloud API ",
        "endpoints": {
            "POST /chat":               "محادثة نصية",
            "POST /meta/webhook":       "Meta WhatsApp Webhook",
            "GET  /meta/webhook":       "Meta Webhook Verification",
            "GET  /meta/status":        "حالة Meta",
            "GET  /admin/analytics/summary": "ملخص الإحصائيات",
            "CRUD /admin/products":     "إدارة المنتجات",
            "CRUD /admin/stores":       "إدارة المتاجر",
            "CRUD /admin/orders":       "إدارة الطلبات",
        },
    }


@app.get("/health", tags=["System"])
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}