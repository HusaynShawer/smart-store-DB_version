# app/api/routers/chat.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_chat_service
from app.db.session import get_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse, summary="دردش مع المساعد الذكي")
async def chat(
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
    chat_service: ChatService = Depends(get_chat_service),
):
    return await chat_service.process(session, body)