# app/api/routers/admin_stores.py
"""Admin CRUD — /admin/stores."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import StoreModel
from app.db.repositories.store import StoreRepository
from app.schemas.common import DeleteResponse
from app.schemas.serializers import store_to_dict
from app.schemas.store import StoreCreate, StoreOut, StoreUpdate

router = APIRouter(prefix="/admin/stores", tags=["Admin — Stores"])


@router.get("", summary="List stores")
async def list_stores(
    governorate: str | None = Query(None),
    q: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
):
    repo = StoreRepository(db)
    total, rows = await repo.filtered_list(governorate, q, skip, limit)
    return {"total": total, "skip": skip, "limit": limit, "items": [store_to_dict(r) for r in rows]}


@router.get("/{store_id}", response_model=StoreOut, summary="Get one store")
async def get_store(store_id: int, db: AsyncSession = Depends(get_session)):
    row = await StoreRepository(db).get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    return store_to_dict(row)


@router.post("", status_code=201, response_model=StoreOut, summary="Add new store")
async def create_store(body: StoreCreate, db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.add(StoreModel(
        name=body.name, governorate=body.governorate,
        lat=body.lat, lon=body.lon, phone=body.phone,
        products_csv=",".join(body.products),
    ))
    return store_to_dict(row)


@router.put("/{store_id}", response_model=StoreOut, summary="Replace all fields")
async def replace_store(store_id: int, body: StoreCreate, db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    row.name = body.name
    row.governorate = body.governorate
    row.lat = body.lat
    row.lon = body.lon
    row.phone = body.phone
    row.products_csv = ",".join(body.products)
    await repo.flush()
    return store_to_dict(row)


@router.patch("/{store_id}", response_model=StoreOut, summary="Partial update")
async def update_store(store_id: int, body: StoreUpdate, db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    data = body.model_dump(exclude_unset=True)
    if "products" in data and data["products"] is not None:
        data["products_csv"] = ",".join(data.pop("products"))
    for field, value in data.items():
        setattr(row, field, value)
    await repo.flush()
    return store_to_dict(row)


@router.post("/{store_id}/products", response_model=StoreOut, summary="Add a product keyword")
async def add_keyword(store_id: int, keyword: str = Query(...), db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    products = row.products
    if keyword not in products:
        products.append(keyword)
        row.products_csv = ",".join(products)
        await repo.flush()
    return store_to_dict(row)


@router.delete("/{store_id}/products", response_model=StoreOut, summary="Remove a product keyword")
async def remove_keyword(store_id: int, keyword: str = Query(...), db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    row.products_csv = ",".join(p for p in row.products if p != keyword)
    await repo.flush()
    return store_to_dict(row)


@router.delete("/{store_id}", response_model=DeleteResponse, summary="Delete one store")
async def delete_store(store_id: int, db: AsyncSession = Depends(get_session)):
    repo = StoreRepository(db)
    row = await repo.get(store_id)
    if not row:
        raise HTTPException(status_code=404, detail="Store not found")
    await repo.delete(row)
    return DeleteResponse(deleted=True, id=store_id)