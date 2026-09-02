# app/db/repositories/__init__.py
"""Repository pattern — all data access is encapsulated here."""
from app.db.repositories.base import BaseRepository
from app.db.repositories.order import OrderRepository
from app.db.repositories.product import ProductRepository
from app.db.repositories.session import SessionRepository
from app.db.repositories.store import StoreRepository

__all__ = [
    "BaseRepository",
    "OrderRepository",
    "ProductRepository",
    "SessionRepository",
    "StoreRepository",
]