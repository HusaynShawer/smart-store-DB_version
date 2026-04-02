# config/database.py
"""
SQLAlchemy async engine & session factory.
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import (
    Column, Integer, String, Float, Text,
    DateTime, JSON, ForeignKey, func, Boolean
)
from config.settings import get_settings

settings = get_settings()

# ── Engine ────────────────────────────────────────────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base ──────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ══════════════════════════════════════════════════════════════════════════════
# ORM MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ProductModel(Base):
    __tablename__ = "products"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    title       = Column(String(255), nullable=False, index=True)
    price       = Column(Float,       nullable=False)
    category    = Column(String(100), nullable=False, index=True)
    description = Column(Text,        default="")
    image       = Column(String(500), default="")
    rating_rate = Column(Float,       default=0.0)
    rating_count= Column(Integer,     default=0)


class StoreModel(Base):
    __tablename__ = "stores"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False)
    governorate  = Column(String(100), nullable=False, index=True)
    lat          = Column(Float,       nullable=False)
    lon          = Column(Float,       nullable=False)
    phone        = Column(String(30),  nullable=True, comment="Vendor WhatsApp number")
    products_csv = Column(Text, default="")

    @property
    def products(self) -> list[str]:
        return [p.strip() for p in (self.products_csv or "").split(",") if p.strip()]

    @products.setter
    def products(self, value: list[str]):
        self.products_csv = ",".join(value)


class OrderModel(Base):
    __tablename__ = "orders"

    id             = Column(Integer,     primary_key=True, autoincrement=True)
    customer_name  = Column(String(255), nullable=False)
    customer_phone = Column(String(30),  nullable=False, index=True)
    product_id     = Column(String(50),  nullable=False)
    product_name   = Column(String(255), nullable=False)
    product_price  = Column(Float,       nullable=False)
    shop_id        = Column(String(50),  nullable=True)
    product_url    = Column(String(500), nullable=True)
    vendor_phone   = Column(String(30),  nullable=True, comment="Vendor WhatsApp number for this order")
    status         = Column(String(30),  default="pending", index=True)
    notes          = Column(Text,        nullable=True)
    created_at     = Column(DateTime,    server_default=func.now())


class SessionModel(Base):
    __tablename__ = "sessions"

    id         = Column(Integer,  primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, unique=True, index=True)
    messages   = Column(JSON,     default=list)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

async def create_all_tables():
    """Called once at startup — creates tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All SQL tables created / verified.")


async def close_db():
    await engine.dispose()


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async DB session."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise