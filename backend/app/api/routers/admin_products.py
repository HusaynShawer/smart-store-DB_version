# app/api/routers/admin_products.py
"""Admin CRUD — /admin/products."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_product_admin_service
from app.db.session import get_session
from app.db.repositories.product import ProductRepository
from app.schemas.common import DeleteResponse
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.serializers import product_to_dict
from app.services.product_service import ProductAdminService

router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])


@router.get("", summary="List / search products")
async def list_products(
    q: str | None = Query(None),
    category: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    repo = ProductRepository(db)
    total, rows = await repo.filtered_list(q, category, skip, limit)
    return {"total": total, "skip": skip, "limit": limit, "items": [product_to_dict(r) for r in rows]}


@router.get("/{product_id}", response_model=ProductOut, summary="Get one product")
async def get_product(product_id: int, db: AsyncSession = Depends(get_session)):
    row = await ProductRepository(db).get(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_to_dict(row)


@router.post("", status_code=201, response_model=ProductOut, summary="Add new product")
async def create_product(
    body: ProductCreate,
    service: ProductAdminService = Depends(get_product_admin_service),
):
    return product_to_dict(await service.create(body))


@router.put("/{product_id}", response_model=ProductOut, summary="Replace all fields")
async def replace_product(
    product_id: int,
    body: ProductCreate,
    db: AsyncSession = Depends(get_session),
    service: ProductAdminService = Depends(get_product_admin_service),
):
    row = await ProductRepository(db).get(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_to_dict(await service.replace(row, body))


@router.patch("/{product_id}", response_model=ProductOut, summary="Partial update")
async def update_product(
    product_id: int,
    body: ProductUpdate,
    db: AsyncSession = Depends(get_session),
    service: ProductAdminService = Depends(get_product_admin_service),
):
    row = await ProductRepository(db).get(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_to_dict(await service.patch(row, body))


@router.delete("/{product_id}", response_model=DeleteResponse, summary="Delete one product")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_session)):
    repo = ProductRepository(db)
    row = await repo.get(product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    await repo.delete(row)
    return DeleteResponse(deleted=True, id=product_id)


@router.delete("", summary="⚠️ Delete ALL products")
async def delete_all_products(
    confirm: bool = Query(False),
    db: AsyncSession = Depends(get_session),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass ?confirm=true")
    deleted = await ProductRepository(db).delete_all()
    return {"deleted": deleted}