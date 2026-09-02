# app/core/llm.py
"""
LLM integration for the agent.

The agent uses `deepseek-v4-flash-0731` served through the OpenAI-compatible
endpoint at `https://backend.sovereigneg.com/v1` (apiKey from env
SOVEREIGNEG_API_KEY). We call the OpenAI-compatible chat/completions API
directly over httpx: the SovereignEG endpoint returns `"role": null` in its
message payload, which breaks `langchain_openai`'s strict response parser,
so a thin transport is both more robust and dependency-light.
"""
import json
import logging
from functools import lru_cache

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class LLMError(RuntimeError):
    """Raised when the model endpoint returns a non-success response."""


@lru_cache(maxsize=1)
def get_chat_llm() -> "ChatLLM":
    """Cached singleton chat model (Factory accessor)."""
    return ChatLLM()


class ChatLLM:
    """Minimal OpenAI-compatible chat client (async, role-null tolerant)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.SOVEREIGNEG_API_KEY
        self._model = model or settings.LLM_MODEL
        self._temperature = settings.LLM_TEMPERATURE if temperature is None else temperature
        self._timeout = timeout

    async def acomplete(self, system: str, user: str) -> str:
        """One-shot chat completion (system + user message)."""
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = await self._post(payload)
        try:
            content = data["choices"][0]["message"].get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Unexpected response shape: {data}") from exc
        return str(content or "")

    async def _post(self, payload: dict) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key or 'EMPTY_API_KEY'}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
        if response.status_code != 200:
            raise LLMError(
                f"LLM HTTP {response.status_code}: {response.text[:400]}"
            )
        return response.json()

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Best-effort extraction of a JSON object from a model reply."""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        candidates = text.split("```")
        for block in candidates:
            block = block.strip()
            if block.startswith("json"):
                block = block[4:]
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        return None

    async def acomplete_json(self, system: str, user: str) -> dict | None:
        """Ask the model for a single JSON object and parse it robustly."""
        instruction = (
            "\n\nRespond with a single valid JSON object. "
            "Do not add text outside the JSON."
        )
        try:
            raw = await self.acomplete(system, user + instruction)
            return self._extract_json(raw)
        except Exception as exc:  # network / http / parse errors
            logger.warning("JSON completion failed: %s", exc)
            return None