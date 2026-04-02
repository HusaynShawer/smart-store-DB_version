# routes/sessions.py
"""
Admin CRUD — /admin/sessions
GET    /admin/sessions                      → list all
GET    /admin/sessions/{session_id}         → full history
PATCH  /admin/sessions/{session_id}/clear   → clear messages
DELETE /admin/sessions/{session_id}         → delete
DELETE /admin/sessions                      → ⚠️ delete all
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from datetime import datetime, timezone

from config.database import get_session, SessionModel
from models.schemas import DeleteResponse

router = APIRouter(prefix="/admin/sessions", tags=["Admin — Sessions"])


def _out(row: SessionModel) -> dict:
    return {
        "id":         row.id,
        "session_id": row.session_id,
        "messages":   row.messages or [],
        "msg_count":  len(row.messages or []),
        "updated_at": row.updated_at,
    }


@router.get("", summary="List all sessions")
async def list_sessions(
    skip:  int = Query(0,  ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    stmt  = select(SessionModel).order_by(SessionModel.updated_at.desc())
    total = (await db.execute(select(func.count()).select_from(SessionModel))).scalar_one()
    rows  = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    # Return summary (no messages body) for list view
    items = [
        {"id": r.id, "session_id": r.session_id,
         "msg_count": len(r.messages or []), "updated_at": r.updated_at}
        for r in rows
    ]
    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/{session_id}", summary="Get full session history")
async def get_session_history(session_id: str, db: AsyncSession = Depends(get_session)):
    stmt = select(SessionModel).where(SessionModel.session_id == session_id)
    row  = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return _out(row)


@router.patch("/{session_id}/clear", summary="Clear messages, keep session")
async def clear_session(session_id: str, db: AsyncSession = Depends(get_session)):
    stmt = select(SessionModel).where(SessionModel.session_id == session_id)
    row  = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    row.messages   = []
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"cleared": True, "session_id": session_id}


@router.delete("/{session_id}", response_model=DeleteResponse, summary="Delete one session")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_session)):
    stmt = select(SessionModel).where(SessionModel.session_id == session_id)
    row  = (await db.execute(stmt)).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(row)
    return DeleteResponse(deleted=True, id=session_id)


@router.delete("", summary="⚠️ Delete ALL sessions")
async def delete_all_sessions(
    confirm: bool = Query(False),
    db: AsyncSession = Depends(get_session),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass ?confirm=true to delete all sessions")
    result = await db.execute(delete(SessionModel))
    return {"deleted": result.rowcount}
