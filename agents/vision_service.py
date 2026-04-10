# agents/vision_service.py
"""
VisionService — بيحلل الصور عن طريق Groq Vision (Llama 4 Scout).
يفهم المنتج في الصورة ويرجع query نصي لـ QueryUnderstanding يفهمه.
"""
import base64
import logging
from pathlib import Path
from groq import Groq
from config.settings import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)

MAX_SIZE   = 10 * 1024 * 1024
_EXT_MIME  = {
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
    "png":  "image/png",
    "webp": "image/webp",
}


class VisionService:

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in settings")
        # ✅ Single Groq client — same one used in VoiceService
        self._client = Groq(api_key=settings.GROQ_API_KEY)
        logger.info("[VisionService] Groq Vision ready")

    def analyze(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        """
        يحلل الصورة ويرجع product search query بالإنجليزي.
        النتيجة بتتبعت لـ QueryUnderstanding عشان يفهمها صح.
        مثال: "men blue winter jacket"
        """
        if not image_bytes:
            raise ValueError("image_bytes is empty")
        if len(image_bytes) > MAX_SIZE:
            raise ValueError(f"Image too large ({len(image_bytes)} bytes, max {MAX_SIZE})")

        ext        = Path(filename).suffix.lstrip(".").lower() or "jpg"
        media_type = _EXT_MIME.get(ext, "image/jpeg")
        b64        = base64.b64encode(image_bytes).decode("utf-8")

        logger.info(f"[VisionService] Analyzing {filename} ({len(image_bytes)} bytes)")

        try:
            response = self._client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{b64}"
                                },
                            },
                            {
                                "type": "text",
                                "text": (
                                    "You are a product recognition assistant for an online store. "
                                    "Look at this image and identify the product. "
                                    "Reply with ONLY a short English product search query (3-6 words). "
                                    "Examples: 'men jacket winter coat', 'gaming monitor curved', "
                                    "'gold ring jewelry', 'samsung galaxy smartphone'. "
                                    "No explanation, no punctuation — just the search query."
                                ),
                            },
                        ],
                    }
                ],
                max_tokens=50,
            )

            query = response.choices[0].message.content.strip().lower()
            query = query.strip(".,!?\"'`")
            logger.info(f"[VisionService] Detected: '{query}'")
            return query

        except Exception as exc:
            logger.error(f"[VisionService] Failed: {exc}")
            raise