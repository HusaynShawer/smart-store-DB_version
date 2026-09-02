# tests/test_twilio.py
from app.services.notifications.twilio_service import TwilioService


def test_format_egyptian_numbers():
    svc = TwilioService()
    assert svc.format_phone_number("01001111222") == "+201001111222"
    assert svc.format_phone_number("+201001111222") == "+201001111222"
    assert svc.format_phone_number("201001111222") == "+201001111222"
    assert svc.format_phone_number("1001111222") == "+201001111222"
    assert svc.format_phone_number("") == ""