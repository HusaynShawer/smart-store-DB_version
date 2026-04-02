# routes/stores.py
"""
Admin CRUD — /admin/stores
GET    /admin/stores            → list / filter
GET    /admin/stores/{id}       → get one
POST   /admin/stores            → create
PUT    /admin/stores/{id}       → full replace
PATCH  /admin/stores/{id}       → partial update
POST   /admin/stores/{id}/products  → add keyword
DELETE /admin/stores/{id}/products  → remove keyword
DELETE /admin/stores/{id}       → delete
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from config.database import get_session, StoreModel
from models.schemas import StoreCreate, StoreUpdate, DeleteResponse

router = APIRouter(prefix="/admin/stores", tags=["Admin — Stores"])


def _out(row: StoreModel) -> dict:
    return {
        "id":          row.id,
        "name":        row.name,
        "governorate": row.governorate,
        "lat":         row.lat,
        "lon":         row.lon,
        "phone":       row.phone,
        "products":    row.products,
    }


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", summary="List stores")
async def list_stores(
    governorate: Optional[str] = Query(None),
    q:           Optional[str] = Query(None, description="Search by name"),
    skip:        int = Query(0,  ge=0),
    limit:       int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(StoreModel)
    if governorate:
        stmt = stmt.where(StoreModel.governorate.ilike(f"%{governorate}%"))
    if q:
        stmt = stmt.where(StoreModel.name.ilike(f"%{q}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows  = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    return {"total": total, "skip": skip, "limit": limit, "items": [_out(r) for r in rows]}


# ── Get one ───────────────────────────────────────────────────────────────────

@router.get("/{id}", summary="Get one store")
async def get_store(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    return _out(row)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Add new store")
async def create_store(body: StoreCreate, db: AsyncSession = Depends(get_session)):
    row = StoreModel(
        name=body.name,
        governorate=body.governorate,
        lat=body.lat,
        lon=body.lon,
        phone=body.phone,
        products_csv=",".join(body.products),
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Full replace ──────────────────────────────────────────────────────────────

@router.put("/{id}", summary="Replace all store fields")
async def replace_store(id: int, body: StoreCreate, db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    row.name         = body.name
    row.governorate  = body.governorate
    row.lat          = body.lat
    row.lon          = body.lon
    row.phone        = body.phone
    row.products_csv = ",".join(body.products)
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Partial update ────────────────────────────────────────────────────────────

@router.patch("/{id}", summary="Update specific fields")
async def update_store(id: int, body: StoreUpdate, db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    if body.name        is not None: row.name        = body.name
    if body.governorate is not None: row.governorate = body.governorate
    if body.lat         is not None: row.lat         = body.lat
    if body.lon         is not None: row.lon         = body.lon
    if body.phone       is not None: row.phone       = body.phone
    if body.products    is not None: row.products_csv = ",".join(body.products)
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Add product keyword ───────────────────────────────────────────────────────

@router.post("/{id}/products", summary="Add a product keyword to store")
async def add_keyword(id: int, keyword: str = Query(...), db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    current = row.products
    if keyword not in current:
        current.append(keyword)
        row.products_csv = ",".join(current)
        await db.flush()
        await db.refresh(row)
    return _out(row)


# ── Remove product keyword ────────────────────────────────────────────────────

@router.delete("/{id}/products", summary="Remove a product keyword from store")
async def remove_keyword(id: int, keyword: str = Query(...), db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    current = [k for k in row.products if k != keyword]
    row.products_csv = ",".join(current)
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{id}", response_model=DeleteResponse, summary="Delete one store")
async def delete_store(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(StoreModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    await db.delete(row)
    return DeleteResponse(deleted=True, id=id)
