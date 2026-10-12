# app/schemas/session.py
from datetime import datetime

from pydantic import BaseModel


class SessionSummary(BaseModel):
    id: int
    session_id: str
    msg_count: int
    updated_at: datetime | None = None


class SessionOut(SessionSummary):
    messages: list[dict] = []


class SessionList(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[SessionSummary]