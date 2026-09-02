# app/services/vision_service.py
"""VisionService — product recognition from an image via Gemini."""
import asyncio

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_VISION_PROMPT = (
    "You are a product recognition assistant for an online store. "
    "Look at this image and identify the product TYPE and BRAND. "
    "Reply with ONLY a short English product search query (3-6 words) focused on "
    "the product category, NOT an exact model. "
    "If you are not 100% sure of the exact model, just say the brand and type "
    "instead (e.g. 'iphone smartphone' not 'iphone 15 pro max'). "
    "Examples: 'apple iphone smartphone', 'mens leather jacket', 'titanium watch', "
    "'gold ring jewelry'. No explanation, just the search query."
)

MAX_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class VisionService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def analyze(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """Return a short English product search query extracted from the image."""
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=[part, _VISION_PROMPT],
        )
        query = (response.text or "").strip()
        if not query:
            raise ValueError("Gemini vision returned an empty query.")
        logger.info("Vision detected: '%s'", query)
        return query