# tests/test_location.py
from app.services.location_service import (
    GOVERNORATES,
    haversine,
    resolve_location,
    sort_stores_by_distance,
)


def test_resolve_location_arabic_and_english():
    assert resolve_location("قنا") == GOVERNORATES["قنا"]
    assert resolve_location("أنا في القاهرة دلوقتي") == GOVERNORATES["القاهرة"]
    assert resolve_location("qena") == GOVERNORATES["qena"]
    assert resolve_location("باريس") is None


def test_haversine_known_distance():
    # Cairo → Alexandria ≈ 210 km
    distance = haversine(30.0444, 31.2357, 31.2001, 29.9187)
    assert 170 <= distance <= 230


def test_sort_stores_by_distance():
    stores = [
        {"name": "far", "lat": 31.2, "lon": 29.9},
        {"name": "near", "lat": 30.05, "lon": 31.24},
    ]
    ordered = sort_stores_by_distance(stores, 30.0444, 31.2357)
    assert ordered[0]["name"] == "near"
    assert "distance_km" in ordered[0]

def test_format_stores_message():
    from app.services.location_service import format_stores_message

    text = format_stores_message([], "phone")
    assert "عذراً" in text