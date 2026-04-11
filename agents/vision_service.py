"""
VisionService — بيحلل الصور عن طريق Gemini Vision (Gemma).
يفهم المنتج في الصورة ويرجع query نصي لـ QueryUnderstanding يفهمه.
"""

import io
import logging
from pathlib import Path

from PIL import Image

from config.settings import get_settings
from config.models_config import VISION_MODEL, VISION_MAX_TOKENS

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_SIZE = 10 * 1024 * 1024
_EXT_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}
ALLOWED_EXT   = set(_EXT_MIME.keys())    # {"jpg", "jpeg", "png", "webp"}
ALLOWED_TYPES = set(_EXT_MIME.values())  # {"image/jpeg", "image/png", "image/webp"}


class VisionService:
    """Service for analyzing product images using Gemini Vision API."""

    def __init__(self):
        """Initialize Gemini client."""
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in settings")
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._client = genai
            self._model = genai.GenerativeModel(VISION_MODEL)
            logger.info("[VisionService] Gemini Vision ready")
        except ImportError:
            logger.error("google-generativeai not installed. Run: pip install google-generativeai")
            raise

    def analyze(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        """
        Analyze image and return product search query in English.
        
        The result is sent to QueryUnderstanding for proper parsing.
        Example: "men blue winter jacket"
        
        Args:
            image_bytes: Raw image bytes
            filename: Original filename for MIME type detection
            
        Returns:
            English search query string
        """
        if not image_bytes:
            raise ValueError("image_bytes is empty")
        if len(image_bytes) > MAX_SIZE:
            raise ValueError(f"Image too large ({len(image_bytes)} bytes, max {MAX_SIZE})")

        ext = Path(filename).suffix.lstrip(".").lower() or "jpg"
        media_type = _EXT_MIME.get(ext, "image/jpeg")

        logger.info(f"[VisionService] Analyzing {filename} ({len(image_bytes)} bytes)")

        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert RGBA to RGB if needed
            if image.mode == 'RGBA':
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3])
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')

            # Generate content with Gemini
            response = self._model.generate_content(
                contents=[
                    "You are a product recognition assistant for an online store. "
                    "Look at this image and identify the product. "
                    "Reply with ONLY a short English product search query (3-6 words). "
                    "Examples: 'men jacket winter coat', 'gaming monitor curved', "
                    "'gold ring jewelry', 'samsung galaxy smartphone'. "
                    "No explanation, no punctuation — just the search query.",
                    image
                ],
                generation_config=self._client.GenerationConfig(
                    max_output_tokens=VISION_MAX_TOKENS,
                    temperature=0.1,
                )
            )

            query = response.text.strip().lower() if response.text else ""
            query = query.strip(".,!?\"'`")
            logger.info(f"[VisionService] Detected: '{query}'")
            return query if query else "unknown product"

        except Exception as exc:
            logger.error(f"[VisionService] Failed: {exc}", exc_info=True)
            raise