# app/schemas/product.py
from pydantic import BaseModel, Field, ConfigDict


class Rating(BaseModel):
    rate: float = 0.0
    count: int = 0


class ProductOut(BaseModel):
    """Serialized product + optional store enrichment from the agent."""

    model_config = ConfigDict(extra="ignore")

    id: int
    title: str
    price: float
    category: str
    description: str = ""
    image: str = ""
    rating: Rating = Field(default_factory=Rating)

    # Enrichment (populated by the agent's nearby/search flow)
    shop_id: int | None = None
    shop_name: str | None = None
    shop_governorate: str | None = None
    shop_phone: str | None = None
    shop_distance: float | None = None
    product_url: str | None = None


class ProductCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    price: float = Field(ge=0)
    category: str = Field(min_length=1, max_length=100)
    description: str = ""
    image: str = ""
    rating: Rating = Field(default_factory=Rating)


class ProductUpdate(BaseModel):
    title: str | None = None
    price: float | None = Field(default=None, ge=0)
    category: str | None = None
    description: str | None = None
    image: str | None = None
    rating: Rating | None = None


class ProductList(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ProductOut]