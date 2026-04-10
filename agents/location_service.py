# agents/location_service.py
#LocationService 

import math
from typing import Optional


GOVERNORATES: dict[str, tuple[float, float]] = {
    "القاهرة":      (30.0444, 31.2357),
    "الجيزة":       (30.0131, 31.2089),
    "الإسكندرية":   (31.2001, 29.9187),
    "الدقهلية":     (31.0364, 31.3807),
    "البحر الأحمر": (27.2579, 33.8116),
    "البحيرة":      (30.8480, 30.3436),
    "الفيوم":       (29.3084, 30.8428),
    "الغربية":      (30.8753, 31.0364),
    "الإسماعيلية":  (30.5965, 32.2715),
    "المنوفية":     (30.5973, 30.9876),
    "المنيا":       (28.1099, 30.7503),
    "القليوبية":    (30.3292, 31.2169),
    "الوادي الجديد":(25.4890, 29.1567),
    "السويس":       (29.9737, 32.5270),
    "اسوان":        (24.0889, 32.8998),
    "أسيوط":        (27.1809, 31.1837),
    "بني سويف":     (29.0661, 31.0994),
    "بورسعيد":      (31.2653, 32.3019),
    "دمياط":        (31.4165, 31.8133),
    "الشرقية":      (30.7226, 31.7180),
    "جنوب سيناء":   (29.3100, 34.1500),
    "كفر الشيخ":    (31.1107, 30.9388),
    "مطروح":        (31.3525, 27.2453),
    "الأقصر":       (25.6872, 32.6396),
    "قنا":          (26.1551, 32.7160),
    "شمال سيناء":   (30.2850, 33.6150),
    "سوهاج":        (26.5569, 31.6948),
    "cairo":        (30.0444, 31.2357),
    "alex":         (31.2001, 29.9187),
    "luxor":        (25.6872, 32.6396),
    "aswan":        (24.0889, 32.8998),
    "qena":         (26.1551, 32.7160),
    "sohag":        (26.5569, 31.6948),
    "asyut":        (27.1809, 31.1837),
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
  
    R = 6371 
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def resolve_location(location_text: str) -> Optional[tuple[float, float]]:
  
    text = location_text.strip().lower()

    for name, coords in GOVERNORATES.items():
        if text == name.lower() or text in name.lower() or name.lower() in text:
            return coords

    return None


def sort_stores_by_distance(
    stores: list[dict],
    user_lat: float,
    user_lon: float,
) -> list[dict]:
   
    for store in stores:
        store_lat = store.get("lat", 0)
        store_lon = store.get("lon", 0)
        store["distance_km"] = round(
            haversine(user_lat, user_lon, store_lat, store_lon), 1
        )

    return sorted(stores, key=lambda s: s["distance_km"])


def format_stores_message(stores: list[dict], product_name: str) -> str:
    if not stores:
        return f"عذراً، مفيش متاجر متاحة تحمل '{product_name}' دلوقتي."

    lines = [f"🏪 المتاجر اللي عندها '{product_name}' مرتبة من الأقرب ليك:\n"]
    for i, store in enumerate(stores[:5], 1):
        dist = store.get("distance_km", "?")
        gov  = store.get("governorate", "")
        name = store.get("name", "متجر")
        phone = store.get("phone", "")
        lines.append(
            f"{i}.  {name} — {gov}\n"
            f"    المسافة: {dist} كم\n"
            f"    {phone}\n"
        )

    return "\n".join(lines)