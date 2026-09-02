# tests/test_schemas.py
import pytest
from pydantic import ValidationError

from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.product import ProductCreate


def test_chat_request_required_message():
    with pytest.raises(ValidationError):
        ChatRequest(message="")

    req = ChatRequest(message="عايز موبايل", session_id="s1")
    assert req.session_id == "s1"


def test_chat_response_optional_fields():
    res = ChatResponse(response="مرحبا")
    assert res.state == "conversation"
    assert res.products is None
    assert res.nearby_stores is None


def test_product_create_validation():
    with pytest.raises(ValidationError):
        ProductCreate(title="", price=-1, category="")


def test_product_accepts_rating_nested():
    p = ProductCreate(title="x", price=5, category="c", rating={"rate": 4.2, "count": 3})
    assert p.rating.rate == 4.2