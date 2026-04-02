# routes/orders.py
"""
Admin CRUD — /admin/orders
GET    /admin/orders        → list (filter status / phone)
GET    /admin/orders/{id}   → get one
POST   /admin/orders        → create manually
PATCH  /admin/orders/{id}   → update status / notes
DELETE /admin/orders/{id}   → delete
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from typing import Optional

from config.database import get_session, OrderModel
from models.schemas import OrderCreate, OrderUpdate, DeleteResponse

router = APIRouter(prefix="/admin/orders", tags=["Admin — Orders"])


def _out(row: OrderModel) -> dict:
    return {
        "id":             row.id,
        "customer_name":  row.customer_name,
        "customer_phone": row.customer_phone,
        "product_id":     row.product_id,
        "product_name":   row.product_name,
        "product_price":  row.product_price,
        "shop_id":        row.shop_id,
        "product_url":    row.product_url,
        "status":         row.status,
        "notes":          row.notes,
        "created_at":     row.created_at,
    }


@router.get("", summary="List orders")
async def list_orders(
    status: Optional[str] = Query(None, example="pending"),
    phone:  Optional[str] = Query(None),
    skip:   int = Query(0,  ge=0),
    limit:  int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(OrderModel).order_by(OrderModel.created_at.desc())
    if status:
        stmt = stmt.where(OrderModel.status == status)
    if phone:
        stmt = stmt.where(OrderModel.customer_phone.ilike(f"%{phone}%"))

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows  = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    return {"total": total, "skip": skip, "limit": limit, "items": [_out(r) for r in rows]}


@router.get("/{id}", summary="Get one order")
async def get_order(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(OrderModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return _out(row)


@router.post("", status_code=201, summary="Create order manually")
async def create_order(body: OrderCreate, db: AsyncSession = Depends(get_session)):
    row = OrderModel(**body.model_dump(), status="pending")
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return _out(row)


@router.patch("/{id}", summary="Update status or notes")
async def update_order(id: int, body: OrderUpdate, db: AsyncSession = Depends(get_session)):
    row = await db.get(OrderModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    if body.status is not None: row.status = body.status
    if body.notes  is not None: row.notes  = body.notes
    await db.flush()
    await db.refresh(row)
    return _out(row)


@router.delete("/{id}", response_model=DeleteResponse, summary="Delete one order")
async def delete_order(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(OrderModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    await db.delete(row)
    return DeleteResponse(deleted=True, id=id)
