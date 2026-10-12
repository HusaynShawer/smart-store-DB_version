# app/db/base.py
"""SQLAlchemy declarative base shared by all ORM models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass