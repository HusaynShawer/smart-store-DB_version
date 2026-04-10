
import time
from collections import defaultdict
from config.settings import get_settings

settings = get_settings()

# { phone: [timestamps] }
_request_log: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(phone: str) -> bool:
    """
    يرجع True لو الرقم لسه تحت الحد، False لو وصل الحد.
    """
    now      = time.time()
    window   = 60.0  # ثانية
    max_reqs = settings.RATE_LIMIT_PER_MINUTE

    # امسح الطلبات القديمة
    _request_log[phone] = [t for t in _request_log[phone] if now - t < window]

    if len(_request_log[phone]) >= max_reqs:
        return False

    _request_log[phone].append(now)
    return True


def get_usage(phone: str) -> dict:
    """يجيب معلومات الاستخدام الحالي لرقم معين."""
    now    = time.time()
    window = 60.0
    recent = [t for t in _request_log.get(phone, []) if now - t < window]
    return {
        "phone":      phone,
        "used":       len(recent),
        "limit":      settings.RATE_LIMIT_PER_MINUTE,
        "remaining":  max(0, settings.RATE_LIMIT_PER_MINUTE - len(recent)),
    }