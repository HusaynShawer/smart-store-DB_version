# agents/vision_service.py
"""
VisionService — بيحلل الصور عن طريق Gemini Vision.
يفهم المنتج في الصورة ويرجع وصف نصي للـ Agent يبحث بيه.
"""
import base64
import google.generativeai as genai
from config.settings import get_settings

settings = get_settings()

MAX_SIZE       = 10 * 1024 * 1024   # 10 MB
ALLOWED_TYPES  = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_EXT    = {".jpg", ".jpeg", ".png", ".webp"}


class VisionService:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self._client = genai.GenerativeModel('gemini-1.5-flash')

    def analyze(self, image_bytes: bytes, filename: str = "image.jpg") -> str:
        """
        يحلل الصورة ويرجع وصف المنتج كنص.
        مثال: "blue men's jacket winter coat"
        """
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        media_type = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"

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
                            }
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are a product recognition assistant for an online store. "
                                "Look at this image and identify the product. "
                                "Reply with ONLY a short product search query in English (3-6 words). "
                                "Examples: 'men jacket winter coat', 'gaming monitor curved', 'gold ring jewelry'. "
                                "No explanation, just the search query."
                            )
                        }
                    ]
                }
            ],
            max_tokens=50,
        )

        query = response.choices[0].message.content.strip()
        print(f"[VisionService] Detected product: '{query}'")
        return query