"""
QueryUnderstanding — بيفهم قصد المستخدم قبل البحث.

Uses Gemini/Gemma for text understanding (no Groq dependency).
"""

import json
import logging
import re
from functools import lru_cache
from typing import Optional, Dict, Tuple, List

from config.settings import get_settings
from config.models_config import (
    INTENT_MODEL,
    INTENT_TEMPERATURE,
    INTENT_MAX_TOKENS,
)
from agents.arabic_normalizer import normalize

settings = get_settings()
logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "electronics", "jewelery", "men's clothing", "women's clothing",
    "beauty", "fragrances", "furniture", "groceries",
}

FAST_LOOKUP: Dict[str, Tuple[str, List[str], List[str]]] = {
    "iphone": ("electronics", ["iphone", "apple", "phone"], ["ايفون", "آيفون"]),
    "samsung": ("electronics", ["samsung", "galaxy", "phone"], ["سامسونج"]),
    "macbook": ("electronics", ["macbook", "laptop", "apple"], ["ماك بوك"]),
    "mac": ("electronics", ["macbook", "laptop", "apple"], ["ماك"]),
    "laptop": ("electronics", ["laptop", "computer"], ["لابتوب"]),
    "mobile": ("electronics", ["phone", "mobile"], ["موبايل"]),
    "phone": ("electronics", ["phone", "mobile"], ["موبايل"]),
    "ايفون": ("electronics", ["iphone", "apple"], ["ايفون"]),
    "سامسونج": ("electronics", ["samsung", "galaxy"], ["سامسونج"]),
    "لابتوب": ("electronics", ["laptop", "computer"], ["لابتوب"]),
    "موبايل": ("electronics", ["phone", "mobile"], ["موبايل"]),
    "خاتم": ("jewelery", ["ring", "gold"], ["خاتم"]),
    "ذهب": ("jewelery", ["gold", "ring"], ["ذهب"]),
    "جاكيت": ("men's clothing", ["jacket", "coat"], ["جاكيت"]),
}

_SYSTEM_PROMPT = """You are a search query understanding assistant for an Egyptian e-commerce store (متجر زكي).
Return ONLY a JSON object with no markdown:
{"category": "", "terms": [], "synonyms": [], "brand": "", "intent": ""}
Terms must be in English, synonyms in Arabic."""


def _check_fast_path(query: str) -> Optional[dict]:
    tokens = query.lower().split()
    for token in tokens:
        if token in FAST_LOOKUP:
            category, terms, synonyms = FAST_LOOKUP[token]
            return {"category": category, "terms": terms, "synonyms": synonyms, "brand": terms[0], "intent": " ".join(terms)}
    return None


def _call_gemini(query: str) -> str:
    """Call Gemini/Gemma API for query understanding."""
    try:
        import google.generativeai as genai
    except ImportError:
        logger.error("google-generativeai not installed. Run: pip install google-generativeai")
        raise
    
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(INTENT_MODEL)
    
    response = model.generate_content(
        contents=[
            {"role": "user", "parts": [_SYSTEM_PROMPT]},
            {"role": "user", "parts": [query]}
        ],
        generation_config=genai.GenerationConfig(
            temperature=INTENT_TEMPERATURE,
            max_output_tokens=INTENT_MAX_TOKENS,
        )
    )
    return response.text


def _cached_understand(query_normalized: str) -> str:
    return _call_gemini(query_normalized)


_cached_understand_lru = lru_cache(maxsize=512)(_cached_understand)


class QueryUnderstanding:
    def __init__(self):
        self._client = None
        if settings.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._client = genai
                logger.info("[QueryUnderstanding] Gemini client ready")
            except ImportError:
                logger.warning("[QueryUnderstanding] google-generativeai not installed")
        else:
            logger.warning("[QueryUnderstanding] No GEMINI_API_KEY, using FAST_LOOKUP fallback")

    def understand(self, query: str) -> dict:
        if not query or not query.strip():
            return {"category": None, "terms": [], "synonyms": [], "brand": None, "intent": ""}

        query_normalized = normalize(query)
        
        # Fast path for common terms
        fast_result = _check_fast_path(query_normalized)
        if fast_result:
            return fast_result

        # Fallback if no Gemini key
        if not settings.GEMINI_API_KEY:
            return {
                "category": None,
                "terms": [t for t in query_normalized.lower().split() if len(t) > 2],
                "synonyms": [],
                "brand": None,
                "intent": query,
            }

        try:
            raw = _cached_understand_lru(query_normalized)
            raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
            parsed = json.loads(raw)
            
            return {
                "category": parsed.get("category") if parsed.get("category") in VALID_CATEGORIES else None,
                "terms": [str(t).lower().strip() for t in parsed.get("terms", []) if t],
                "synonyms": [str(s).strip() for s in parsed.get("synonyms", []) if s],
                "brand": parsed.get("brand"),
                "intent": parsed.get("intent", query),
            }
        except Exception as exc:
            logger.warning(f"[QU] Gemini failed: {exc}")
            return {
                "category": None,
                "terms": [t for t in query_normalized.lower().split() if len(t) > 2],
                "synonyms": [],
                "brand": None,
                "intent": query,
            }


_qu: Optional[QueryUnderstanding] = None

def get_query_understanding() -> QueryUnderstanding:
    global _qu
    if _qu is None:
        _qu = QueryUnderstanding()
    return _qu
