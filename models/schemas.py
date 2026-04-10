# models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


# Enums for conversation states
class ConversationState(str, Enum):
    GREETING         = "greeting"
    SEARCHING        = "searching"
    PRODUCT_FOUND    = "product_found"
    AWAITING_CONFIRM = "awaiting_confirm"
    ORDER_SENT       = "order_sent"
    LOCATING         = "locating"
    ERROR            = "error"


# Chat Request/Response Models
class ChatRequest(BaseModel):
    message: str = Field(..., example="I need a phone in Cairo")
    session_id: Optional[str] = Field(None, example="user-123")
    customer_name: Optional[str] = Field(None, example="Ahmed Mohamed")
    customer_phone: Optional[str] = Field(None, example="01012345678")
    selected_product: Optional[Dict[str, Any]] = Field(None)
    location_text: Optional[str] = Field(None, example="Cairo")
    latitude: Optional[float] = Field(None, example=26.1551)
    longitude: Optional[float] = Field(None, example=32.7160)


class StoreResult(BaseModel):
    id: str
    name: str
    governorate: str
    phone: Optional[str] = None
    distance_km: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    state: ConversationState
    products: Optional[List[Dict[str, Any]]] = None
    order_confirmation: Optional[Dict[str, Any]] = None
    nearby_stores: Optional[List[StoreResult]] = None


# Product Models
class RatingSchema(BaseModel):
    rate: float = 0.0
    count: int = 0


class ProductCreate(BaseModel):
    title: str
    price: float
    category: str
    description: str = ""
    image: str = ""
    rating: RatingSchema = Field(default_factory=RatingSchema)


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    rating: Optional[RatingSchema] = None


class ProductOut(BaseModel):
    id: int
    title: str
    price: float
    category: str
    description: str
    image: str
    rating: RatingSchema

    model_config = {"from_attributes": True}


# Store Models
class StoreCreate(BaseModel):
    name: str
    governorate: str
    lat: float
    lon: float
    phone: Optional[str] = None
    products: List[str] = Field(default_factory=list,
                                 example=["phone", "laptop", "mobile"])


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    governorate: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    phone: Optional[str] = None
    products: Optional[List[str]] = None


class StoreOut(BaseModel):
    id: int
    name: str
    governorate: str
    lat: float
    lon: float
    phone: Optional[str] = None
    products: List[str] = []

    model_config = {"from_attributes": True}


# ── Order ─────────────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    product_id: str
    product_name: str
    product_price: float
    shop_id: Optional[str] = None
    product_url: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    customer_name: str
    customer_phone: str
    product_id: str
    product_name: str
    product_price: float
    shop_id: Optional[str] = None
    product_url: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Session ───────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    id: int
    session_id: str
    messages: List[Dict[str, str]] = []
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Generic ───────────────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    deleted: bool
    id: Any


class PaginatedResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[Any]
