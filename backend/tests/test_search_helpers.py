# tests/test_search_helpers.py
from app.services.search_service import translate


def test_translate_arabic_keywords():
    assert translate("موبايل") == "phone"
    assert translate("لابتوب جديد") == "laptop جديد"
    assert translate("خاتم دهب") == "ring دهب"


def test_keep_english():
    assert translate("laptop") == "laptop"
    assert translate("I want a phone") == "i want a phone"