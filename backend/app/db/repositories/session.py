# app/db/repositories/session.py
"""SessionRepository — chat-history persistence (last N messages)."""
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SessionModel
from app.db.repositories.base import BaseRepository


class SessionRepository(BaseRepository[SessionModel]):
    model = SessionModel

    async def get_messages(self, session_id: str, limit: int = 20) -> list[dict]:
        row = await self.get_by_session_id(session_id)
        if not row or not row.messages:
            return []
        return list(row.messages[-limit:])

    async def get_by_session_id(self, session_id: str) -> SessionModel | None:
        stmt = select(SessionModel).where(SessionModel.session_id == session_id)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def append_messages(self, session_id: str, messages: Sequence[dict]) -> None:
        """Append user/assistant turns, keeping only the last 20."""
        row = await self.get_by_session_id(session_id)
        if row:
            existing = list(row.messages or [])
            existing.extend(messages)
            row.messages = existing[-20:]
            row.updated_at = datetime.now(timezone.utc)
        else:
            row = SessionModel(
                session_id=session_id,
                messages=list(messages),
                updated_at=datetime.now(timezone.utc),
            )
            self._session.add(row)
        await self._session.flush()

    async def clear(self, session_id: str) -> bool:
        row = await self.get_by_session_id(session_id)
        if not row:
            return False
        row.messages = []
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True

    async def summary_list(
        self, skip: int, limit: int
    ) -> tuple[int, list[dict]]:
        stmt = select(SessionModel).order_by(SessionModel.updated_at.desc())
        total = int((await self._session.execute(select(func.count()).select_from(SessionModel))).scalar_one())
        rows = list((await self._session.execute(stmt.offset(skip).limit(limit))).scalars().all())
        items = [
            {
                "id": r.id,
                "session_id": r.session_id,
                "msg_count": len(r.messages or []),
                "updated_at": r.updated_at,
            }
            for r in rows
        ]
        return total, items