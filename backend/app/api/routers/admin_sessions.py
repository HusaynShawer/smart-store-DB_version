# app/api/routers/admin_sessions.py
"""Admin CRUD — /admin/sessions."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.repositories.session import SessionRepository
from app.schemas.common import DeleteResponse
from app.schemas.serializers import session_to_dict

router = APIRouter(prefix="/admin/sessions", tags=["Admin — Sessions"])


@router.get("", summary="List all sessions")
async def list_sessions(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_session),
):
    total, items = await SessionRepository(db).summary_list(skip, limit)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{session_id}", summary="Get full session history")
async def get_session_history(session_id: str, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    row = await repo.get_by_session_id(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_to_dict(row)


@router.patch("/{session_id}/clear", summary="Clear messages, keep session")
async def clear_session(session_id: str, db: AsyncSession = Depends(get_session)):
    cleared = await SessionRepository(db).clear(session_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"cleared": True, "session_id": session_id}


@router.delete("/{session_id}", response_model=DeleteResponse, summary="Delete one session")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    row = await repo.get_by_session_id(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    await repo.delete(row)
    return DeleteResponse(deleted=True, id=session_id)


@router.delete("", summary="⚠️ Delete ALL sessions")
async def delete_all_sessions(confirm: bool = False, db: AsyncSession = Depends(get_session)):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass ?confirm=true")
    deleted = await SessionRepository(db).delete_all()
    return {"deleted": deleted}