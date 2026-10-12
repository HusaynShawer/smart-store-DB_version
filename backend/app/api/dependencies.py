# app/api/dependencies.py
"""Shared FastAPI dependencies (Dependency Injection)."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.chat_service import ChatService
from app.services.product_service import ProductAdminService
from app.services.vision_service import VisionService
from app.services.voice_service import VoiceService


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    return ChatService()


@lru_cache(maxsize=1)
def get_voice_service() -> VoiceService:
    return VoiceService()


@lru_cache(maxsize=1)
def get_vision_service() -> VisionService:
    return VisionService()


def get_product_admin_service(
    session: AsyncSession = Depends(get_session),
) -> ProductAdminService:
    return ProductAdminService(session)