# app/schemas/store.py
from pydantic import BaseModel, Field


class StoreOut(BaseModel):
    id: int
    name: str
    governorate: str
    lat: float
    lon: float
    phone: str | None = None
    products: list[str] = Field(default_factory=list)
    distance_km: float | None = None


class StoreCreate(BaseModel):
    name: str = Field(min_length=1)
    governorate: str = Field(min_length=1)
    lat: float
    lon: float
    phone: str | None = None
    products: list[str] = Field(default_factory=list)


class StoreUpdate(BaseModel):
    name: str | None = None
    governorate: str | None = None
    lat: float | None = None
    lon: float | None = None
    phone: str | None = None
    products: list[str] | None = None


class StoreList(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[StoreOut]