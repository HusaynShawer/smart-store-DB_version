# app/db/models.py
"""ORM models — Product, Store, Order, Session (PostgreSQL + pgvector)."""
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()


class ProductModel(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image: Mapped[str] = mapped_column(String(500), default="")
    rating_rate: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)

    # pgvector column — Cohere multilingual embeddings (1024 dims)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(settings.EMBEDDING_DIM), nullable=True
    )


class StoreModel(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    governorate: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Vendor WhatsApp number"
    )
    products_csv: Mapped[Optional[str]] = mapped_column(Text, default="")

    @property
    def products(self) -> list[str]:
        return [p.strip() for p in (self.products_csv or "").split(",") if p.strip()]

    @products.setter
    def products(self, value: list[str]) -> None:
        self.products_csv = ",".join(value)


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_price: Mapped[float] = mapped_column(Float, nullable=False)
    shop_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    product_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    vendor_phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Vendor WhatsApp number for this order"
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now()
    )


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    messages: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )