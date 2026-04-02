# agents/voice_service.py
"""
VoiceService — Speech to Text فقط عن طريق Gemini (or external STT service).
"""
import google.generativeai as genai
from config.settings import get_settings

settings = get_settings()


class VoiceService:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)

    def speech_to_text(self, audio_bytes: bytes, filename: str = "audio.m4a") -> str:
        """
        يحول الصوت لنص عن طريق Groq Whisper.
        بيقبل: mp3, mp4, m4a, wav, webm
        بيكتشف اللغة تلقائياً (عربي أو إنجليزي)
        """
        try:
            transcription = self._client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model="whisper-large-v3",
                language=None,           # auto-detect
                response_format="text",
            )
            return transcription.strip()

        except Exception as exc:
            print(f"[VoiceService] Error: {exc}")
            raise