# app/schemas/serializers.py
"""ORM → dict serializers. Keeps API routers free of mapping logic."""
from app.db.models import OrderModel, ProductModel, SessionModel, StoreModel


def product_to_dict(row: ProductModel) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "price": row.price,
        "category": row.category,
        "description": row.description,
        "image": row.image,
        "rating": {"rate": row.rating_rate, "count": row.rating_count},
    }


def store_to_dict(row: StoreModel, distance_km: float | None = None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "governorate": row.governorate,
        "lat": row.lat,
        "lon": row.lon,
        "phone": row.phone,
        "products": row.products,
        **({"distance_km": distance_km} if distance_km is not None else {}),
    }


def order_to_dict(row: OrderModel) -> dict:
    return {
        "id": row.id,
        "customer_name": row.customer_name,
        "customer_phone": row.customer_phone,
        "product_id": row.product_id,
        "product_name": row.product_name,
        "product_price": row.product_price,
        "shop_id": row.shop_id,
        "product_url": row.product_url,
        "vendor_phone": row.vendor_phone,
        "status": row.status,
        "notes": row.notes,
        "created_at": row.created_at,
    }


def session_to_dict(row: SessionModel) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "messages": row.messages or [],
        "msg_count": len(row.messages or []),
        "updated_at": row.updated_at,
    }