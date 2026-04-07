# routes/analytics.py
"""
Analytics — /admin/analytics
بيعرضلك إحصائيات مهمة:
- أكتر المنتجات اللي بتتبحث عنها
- الطلبات بالمحافظة
- التجار الأكتر مبيعاً
- الرسائل الفاشلة
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from config.database import (
    get_session, SearchLogModel, OrderModel,
    StoreModel, FailedMessageModel
)

router = APIRouter(prefix="/admin/analytics", tags=["Admin — Analytics"])


@router.get("/top-searches")
async def top_searches(
    limit: int = 10,
    db: AsyncSession = Depends(get_session),
):
    """أكتر الكلمات اللي بحث عنها العملاء."""
    stmt   = (
        select(SearchLogModel.query, func.count().label("count"))
        .group_by(SearchLogModel.query)
        .order_by(desc("count"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [{"query": r.query, "count": r.count} for r in result.all()]


@router.get("/orders-by-governorate")
async def orders_by_gov(db: AsyncSession = Depends(get_session)):
    """الطلبات بالمحافظة — من خلال ربط المتاجر بالطلبات."""
    stmt   = (
        select(StoreModel.governorate, func.count(OrderModel.id).label("orders"))
        .join(OrderModel, OrderModel.shop_id == func.cast(StoreModel.id, type_=None), isouter=True)
        .group_by(StoreModel.governorate)
        .order_by(desc("orders"))
    )
    result = await db.execute(stmt)
    return [{"governorate": r.governorate, "orders": r.orders} for r in result.all()]


@router.get("/top-vendors")
async def top_vendors(limit: int = 10, db: AsyncSession = Depends(get_session)):
    """التجار الأكتر استقبالاً للطلبات."""
    stmt   = (
        select(OrderModel.vendor_phone, func.count().label("orders"), func.sum(OrderModel.product_price).label("revenue"))
        .group_by(OrderModel.vendor_phone)
        .order_by(desc("orders"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {"vendor_phone": r.vendor_phone, "orders": r.orders, "revenue": float(r.revenue or 0)}
        for r in result.all()
    ]


@router.get("/failed-messages")
async def failed_messages(db: AsyncSession = Depends(get_session)):
    """الرسائل الفاشلة اللي محتاجة مراجعة."""
    stmt   = select(FailedMessageModel).where(
        FailedMessageModel.is_resolved == False
    ).order_by(desc(FailedMessageModel.created_at)).limit(50)
    result = await db.execute(stmt)
    rows   = result.scalars().all()
    return [
        {
            "id":         r.id,
            "to_phone":   r.to_phone,
            "retries":    r.retries,
            "last_error": r.last_error,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]


@router.post("/retry-failed-messages")
async def retry_failed():
    """يعيد محاولة إرسال الرسائل الفاشلة يدوياً."""
    from agents.meta_service import get_meta_service
    result = await get_meta_service().retry_failed_messages()
    return result


@router.get("/summary")
async def summary(db: AsyncSession = Depends(get_session)):
    """ملخص سريع بكل الأرقام المهمة."""
    total_orders   = (await db.execute(select(func.count(OrderModel.id)))).scalar_one()
    total_stores   = (await db.execute(select(func.count(StoreModel.id)))).scalar_one()
    total_searches = (await db.execute(select(func.count(SearchLogModel.id)))).scalar_one()
    failed_msgs    = (await db.execute(
        select(func.count(FailedMessageModel.id)).where(FailedMessageModel.is_resolved == False)
    )).scalar_one()
    pending_orders = (await db.execute(
        select(func.count(OrderModel.id)).where(OrderModel.status == "pending")
    )).scalar_one()

    return {
        "total_orders":    total_orders,
        "pending_orders":  pending_orders,
        "total_stores":    total_stores,
        "total_searches":  total_searches,
        "failed_messages": failed_msgs,
    }