# agents/voice_service.py
"""
VoiceService — Speech-to-Text عن طريق Groq Whisper large-v3.
بيقبل: mp3, mp4, m4a, wav, webm, ogg
بيكتشف اللغة تلقائياً (عربي أو إنجليزي)
"""
import logging
from groq import Groq
from config.settings import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)

SUPPORTED_FORMATS = {"mp3", "mp4", "m4a", "wav", "webm", "ogg", "flac"}

_EXT_MIME = {
    "mp3":  "audio/mpeg",
    "mp4":  "audio/mp4",
    "m4a":  "audio/mp4",
    "wav":  "audio/wav",
    "webm": "audio/webm",
    "ogg":  "audio/ogg",
    "flac": "audio/flac",
}


class VoiceService:

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in settings")
        self._client = Groq(api_key=settings.GROQ_API_KEY)
        logger.info("[VoiceService] Groq Whisper ready")

    def speech_to_text(self, audio_bytes: bytes, filename: str = "audio.m4a") -> str:
        if not audio_bytes:
            raise ValueError("audio_bytes is empty")

        ext  = filename.rsplit(".", 1)[-1].lower() if "." in filename else "m4a"
        mime = _EXT_MIME.get(ext, "audio/mp4")

        logger.info(f"[VoiceService] Transcribing {filename} ({len(audio_bytes)} bytes)")

        try:
            transcription = self._client.audio.transcriptions.create(
                file=(filename, audio_bytes, mime),
                model="whisper-large-v3",
                language=None,           # auto-detect Arabic / English
                response_format="text",
            )

            text = transcription if isinstance(transcription, str) else (transcription.text or "")
            text = text.strip()
            logger.info(f"[VoiceService] Result: '{text[:100]}'")
            return text

        except Exception as exc:
            logger.error(f"[VoiceService] Failed: {exc}")
            raise