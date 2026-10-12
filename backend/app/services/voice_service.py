# app/services/voice_service.py
"""VoiceService — Speech-to-Text via Gemini (gemini-3.1-flash-lite)."""
import asyncio

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_TRANSCRIBE_PROMPT = (
    "Transcribe the following audio. Keep the original language "
    "(Arabic or English). Output only the transcript, nothing else."
)


class VoiceService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/m4a") -> str:
        """Transcribe audio bytes to text (auto-detects language)."""
        part = types.Part.inline_data(data=audio_bytes, mime_type=mime_type)
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=settings.GEMINI_MODEL,
            contents=[part, _TRANSCRIBE_PROMPT],
        )
        text = (response.text or "").strip()
        if not text:
            raise ValueError("Gemini returned an empty transcription.")
        logger.info("Transcribed %s chars", len(text))
        return text