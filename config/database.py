# config/database.py
import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine,
    create_async_engine, async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import (
    Column, Integer, String, Float, Text,
    DateTime, JSON, func, Boolean, text
)
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

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

class Base(DeclarativeBase):
    pass

class ProductModel(Base):
    __tablename__ = "products"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    title        = Column(String(255), nullable=False, index=True)
    price        = Column(Float,       nullable=False)
    category     = Column(String(100), nullable=False, index=True)
    description  = Column(Text,        default="")
    image        = Column(String(500), default="")
    rating_rate  = Column(Float,       default=0.0)
    rating_count = Column(Integer,     default=0)

class StoreModel(Base):
    __tablename__ = "stores"
    id           = Column(Integer,     primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False)
    governorate  = Column(String(100), nullable=False, index=True)
    lat          = Column(Float,       nullable=False)
    lon          = Column(Float,       nullable=False)
    phone        = Column(String(30),  nullable=True)
    products_csv = Column(Text,        default="")
    is_active    = Column(Boolean,     default=True)

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
    vendor_phone   = Column(String(30),  nullable=True)
    status         = Column(String(30),  default="pending", index=True)
    notes          = Column(Text,        nullable=True)
    created_at     = Column(DateTime,    server_default=func.now())

class SessionModel(Base):
    __tablename__ = "sessions"
    id         = Column(Integer,      primary_key=True, autoincrement=True)
    session_id = Column(String(100),  nullable=False, unique=True, index=True)
    messages   = Column(JSON,         default=list)
    updated_at = Column(DateTime,     server_default=func.now(), onupdate=func.now())

class FailedMessageModel(Base):
    __tablename__ = "failed_messages"
    id           = Column(Integer,     primary_key=True, autoincrement=True)
    to_phone     = Column(String(30),  nullable=False, index=True)
    message_body = Column(Text,        nullable=False)
    retries      = Column(Integer,     default=0)
    last_error   = Column(Text,        nullable=True)
    is_resolved  = Column(Boolean,     default=False)
    created_at   = Column(DateTime,    server_default=func.now())
    updated_at   = Column(DateTime,    server_default=func.now(), onupdate=func.now())

class SearchLogModel(Base):
    __tablename__ = "search_logs"
    id            = Column(Integer,     primary_key=True, autoincrement=True)
    query         = Column(String(500), nullable=False, index=True)
    governorate   = Column(String(100), nullable=True)
    results_count = Column(Integer,     default=0)
    customer_phone= Column(String(30),  nullable=True)
    created_at    = Column(DateTime,    server_default=func.now())


# Migration and initialization functions
async def _migrate_stores_table():
    """
    Add is_active column to stores table if it doesn't exist.
    Resolves: Unknown column 'stores.is_active' in 'field list'
    """
    async with engine.begin() as conn:
        try:
            await conn.execute(text("SELECT is_active FROM stores LIMIT 1"))
            logger.info("Column is_active already exists in stores table")
        except Exception as e:
            try:
                await conn.execute(text(
                    "ALTER TABLE stores ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
                ))
                logger.info("Successfully added is_active column to stores table")
            except Exception as e:
                logger.warning(f"Could not add is_active column: {e}")


async def create_all_tables():
    """Create or verify all database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("All SQL tables created/verified successfully")
        await _migrate_stores_table()
    except Exception as e:
        logger.error("Error creating database tables", exc_info=True)
        raise


async def close_db():
    """Close database engine."""
    try:
        await engine.dispose()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error("Error closing database", exc_info=True)


async def get_session() -> AsyncSession:
    """Get database session for dependency injection."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise