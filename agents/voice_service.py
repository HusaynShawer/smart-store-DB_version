"""
VoiceService — Speech-to-Text عن طريق OpenAI Whisper API.
بيقبل: mp3, mp4, m4a, wav, webm, ogg
بيكتشف اللغة تلقائياً (عربي أو إنجليزي)
"""

import logging
import io

from config.settings import get_settings
from config.models_config import VOICE_MODEL

settings = get_settings()
logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {"mp3", "mp4", "m4a", "wav", "webm", "ogg", "flac"}

_EXT_MIME = {
    "mp3": "audio/mpeg",
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
}


class VoiceService:
    """Service for speech-to-text transcription using OpenAI Whisper API."""

    def __init__(self):
        """Initialize OpenAI client."""
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY not set, voice service disabled")
            self._client = None
            return
            
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("[VoiceService] OpenAI Whisper ready")
        except ImportError:
            logger.error("openai not installed. Run: pip install openai")
            self._client = None

    def speech_to_text(self, audio_bytes: bytes, filename: str = "audio.m4a") -> str:
        """
        Transcribe audio to text using OpenAI Whisper.
        
        Auto-detects language (Arabic/English).
        
        Args:
            audio_bytes: Raw audio bytes
            filename: Original filename for MIME type detection
            
        Returns:
            Transcribed text string
        """
        if not audio_bytes:
            raise ValueError("audio_bytes is empty")
        
        if not self._client:
            raise RuntimeError("Voice service not configured (missing OPENAI_API_KEY)")

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "m4a"
        mime = _EXT_MIME.get(ext, "audio/mp4")

        logger.info(f"[VoiceService] Transcribing {filename} ({len(audio_bytes)} bytes)")

        try:
            # Create file-like object from bytes
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename  # OpenAI client needs filename
            
            transcription = self._client.audio.transcriptions.create(
                model=VOICE_MODEL,
                file=audio_file,
                language=None,  # auto-detect Arabic / English
                response_format="text",
            )

            text = transcription if isinstance(transcription, str) else (transcription.text or "")
            text = text.strip()
            logger.info(f"[VoiceService] Result: '{text[:100]}'" + ("..." if len(text) > 100 else ""))
            return text

        except Exception as exc:
            logger.error(f"[VoiceService] Failed: {exc}", exc_info=True)
            raise
