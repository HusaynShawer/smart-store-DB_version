# app/api/routers/admin_orders.py
"""Admin CRUD — /admin/orders."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OrderModel
from app.db.session import get_session
from app.db.repositories.order import OrderRepository
from app.schemas.common import DeleteResponse
from app.schemas.order import OrderCreate, OrderOut, OrderUpdate
from app.schemas.serializers import order_to_dict

router = APIRouter(prefix="/admin/orders", tags=["Admin — Orders"])


@router.get("", summary="List orders")
async def list_orders(
    status: str | None = Query(None),
    phone: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    total, rows = await OrderRepository(db).filtered_list(status, phone, skip, limit)
    return {"total": total, "skip": skip, "limit": limit, "items": [order_to_dict(r) for r in rows]}


@router.get("/{order_id}", response_model=OrderOut, summary="Get one order")
async def get_order(order_id: int, db: AsyncSession = Depends(get_session)):
    row = await OrderRepository(db).get(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_to_dict(row)


@router.post("", status_code=201, response_model=OrderOut, summary="Create order manually")
async def create_order(body: OrderCreate, db: AsyncSession = Depends(get_session)):
    repo = OrderRepository(db)
    row = await repo.add(OrderModel(**body.model_dump(), status="pending"))
    return order_to_dict(row)


@router.patch("/{order_id}", response_model=OrderOut, summary="Update status / notes")
async def update_order(order_id: int, body: OrderUpdate, db: AsyncSession = Depends(get_session)):
    repo = OrderRepository(db)
    row = await repo.get(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(row, field, value)
    await repo.flush()
    return order_to_dict(row)


@router.delete("/{order_id}", response_model=DeleteResponse, summary="Delete one order")
async def delete_order(order_id: int, db: AsyncSession = Depends(get_session)):
    repo = OrderRepository(db)
    row = await repo.get(order_id)
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    await repo.delete(row)
    return DeleteResponse(deleted=True, id=order_id)