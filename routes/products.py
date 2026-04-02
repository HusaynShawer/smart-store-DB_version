# routes/products.py
"""
Admin CRUD — /admin/products
GET    /admin/products          → list / search
GET    /admin/products/{id}     → get one
POST   /admin/products          → create
PUT    /admin/products/{id}     → full replace
PATCH  /admin/products/{id}     → partial update
DELETE /admin/products/{id}     → delete one
DELETE /admin/products          → ⚠️ delete all
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from typing import Optional

from config.database import get_session, ProductModel
from models.schemas import ProductCreate, ProductUpdate, DeleteResponse

router = APIRouter(prefix="/admin/products", tags=["Admin — Products"])


def _out(row: ProductModel) -> dict:
    return {
        "id":          row.id,
        "title":       row.title,
        "price":       row.price,
        "category":    row.category,
        "description": row.description,
        "image":       row.image,
        "rating": {
            "rate":  row.rating_rate,
            "count": row.rating_count,
        },
    }


# ── List / Search ─────────────────────────────────────────────────────────────

@router.get("", summary="List / search products")
async def list_products(
    q:        Optional[str] = Query(None, description="Search in title / description / category"),
    category: Optional[str] = Query(None),
    skip:     int = Query(0,  ge=0),
    limit:    int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
):
    stmt = select(ProductModel)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                ProductModel.title.ilike(like),
                ProductModel.description.ilike(like),
                ProductModel.category.ilike(like),
            )
        )
    if category:
        stmt = stmt.where(ProductModel.category.ilike(f"%{category}%"))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    rows = (await db.execute(stmt.offset(skip).limit(limit))).scalars().all()
    return {"total": total, "skip": skip, "limit": limit, "items": [_out(r) for r in rows]}


# ── Get one ───────────────────────────────────────────────────────────────────

@router.get("/{id}", summary="Get one product")
async def get_product(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(ProductModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return _out(row)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", status_code=201, summary="Add new product")
async def create_product(body: ProductCreate, db: AsyncSession = Depends(get_session)):
    row = ProductModel(
        title=body.title,
        price=body.price,
        category=body.category,
        description=body.description,
        image=body.image,
        rating_rate=body.rating.rate,
        rating_count=body.rating.count,
    )
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Full replace ──────────────────────────────────────────────────────────────

@router.put("/{id}", summary="Replace all product fields")
async def replace_product(id: int, body: ProductCreate, db: AsyncSession = Depends(get_session)):
    row = await db.get(ProductModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    row.title        = body.title
    row.price        = body.price
    row.category     = body.category
    row.description  = body.description
    row.image        = body.image
    row.rating_rate  = body.rating.rate
    row.rating_count = body.rating.count
    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Partial update ────────────────────────────────────────────────────────────

@router.patch("/{id}", summary="Update specific fields")
async def update_product(id: int, body: ProductUpdate, db: AsyncSession = Depends(get_session)):
    row = await db.get(ProductModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")

    if body.title       is not None: row.title       = body.title
    if body.price       is not None: row.price       = body.price
    if body.category    is not None: row.category    = body.category
    if body.description is not None: row.description = body.description
    if body.image       is not None: row.image       = body.image
    if body.rating      is not None:
        row.rating_rate  = body.rating.rate
        row.rating_count = body.rating.count

    await db.flush()
    await db.refresh(row)
    return _out(row)


# ── Delete one ────────────────────────────────────────────────────────────────

@router.delete("/{id}", response_model=DeleteResponse, summary="Delete one product")
async def delete_product(id: int, db: AsyncSession = Depends(get_session)):
    row = await db.get(ProductModel, id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    await db.delete(row)
    return DeleteResponse(deleted=True, id=id)


# ── Delete all ────────────────────────────────────────────────────────────────

@router.delete("", summary="⚠️ Delete ALL products")
async def delete_all(
    confirm: bool = Query(False, description="Must be true"),
    db: AsyncSession = Depends(get_session),
):
    if not confirm:
        raise HTTPException(status_code=400, detail="Pass ?confirm=true to delete all products")
    result = await db.execute(delete(ProductModel))
    return {"deleted": result.rowcount}
