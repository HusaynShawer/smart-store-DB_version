# app/schemas/order.py
from datetime import datetime

from pydantic import BaseModel, Field


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    product_id: str
    product_name: str
    product_price: float
    shop_id: str | None = None
    product_url: str | None = None
    vendor_phone: str | None = None
    status: str = "pending"
    notes: str | None = None
    created_at: datetime | None = None


class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    product_id: str
    product_name: str
    product_price: float = Field(ge=0)
    shop_id: str | None = None
    product_url: str | None = None
    vendor_phone: str | None = None


class OrderUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class OrderConfirmation(BaseModel):
    """Returned to the client after a successful order."""

    order_id: int
    product_name: str
    product_price: float
    customer_name: str
    customer_phone: str
    vendor_phone: str | None = None
    twilio_sent: bool = False