# agents/query_understanding.py
"""
QueryUnderstanding — بيفهم قصد المستخدم قبل البحث.

بدل ما نعتمد على dictionary ثابت،
بنبعت الـ query للـ LLM يفهمها ويرجعلنا:
  - category  : الكاتيجوري المناسبة
  - terms     : كلمات بحث إنجليزية (multiple)
  - brand     : البراند لو اتذكر
  - intent    : وصف مختصر بالإنجليزي

يتعامل مع:
  ✅ عربي فصيح أو عامي
  ✅ إنجليزي بأخطاء إملائية (labtop, mack poc)
  ✅ أسماء تجارية عربية (ابل، سامسونج، نوكيا)
  ✅ semantic: "شاشة لألعاب" → gaming monitor
"""
import json
import logging
import re
from typing import Optional

from groq import Groq
from config.settings import get_settings

settings = get_settings()
logger   = logging.getLogger(__name__)

VALID_CATEGORIES = {
    "electronics",
    "jewelery",
    "men's clothing",
    "women's clothing",
    "beauty",
    "fragrances",
    "furniture",
    "groceries",
}

_SYSTEM_PROMPT = """
You are a search query understanding assistant for an Egyptian e-commerce store (متجر زكي).
The store sells: electronics, jewelry (jewelery), men's clothing, women's clothing, beauty, fragrances, furniture, groceries.

The user will send a search query in Arabic (formal or Egyptian dialect), English, or mixed.
Your job is to extract the search intent and return a JSON object ONLY — no extra text, no markdown.

JSON format:
{
  "category": "<one of the store categories or null>",
  "terms": ["<english search term 1>", "<english search term 2>", ...],
  "brand": "<brand name in english or null>",
  "intent": "<short description of what user wants, in English>"
}

Rules:
- "terms" must be in ENGLISH and cover synonyms + related models
  Examples:
    "labtop" / "لابتوب" / "كمبيوتر محمول" / "mack poc" → terms: ["laptop", "macbook", "notebook", "computer"]
    "موبايل سامسونج" / "samsung phone"                  → terms: ["samsung", "galaxy", "phone", "smartphone"]
    "خاتم ذهب" / "gold ring"                           → terms: ["gold", "ring", "jewelry", "jewelery"]
    "جاكيت شتوي" / "winter jacket"                      → terms: ["jacket", "winter", "coat", "men's clothing"]
    "ايفون" / "iphone" / "apple phone"                 → terms: ["iphone", "apple", "phone", "smartphone"]
- category must be exactly one of: electronics, jewelery, men's clothing, women's clothing, beauty, fragrances, furniture, groceries — or null
- Fix typos silently (labtop→laptop, mack poc→macbook)
- For vague queries like "هدية" (gift) — return null category and broad terms
- Return ONLY the JSON object. No markdown, no explanation.
""".strip()


class QueryUnderstanding:

    def __init__(self):
        self._client = Groq(api_key=settings.GROQ_API_KEY)

    def understand(self, query: str) -> dict:
        """
        Synchronous wrapper — parses query and returns structured intent.
        Falls back to basic tokenization if LLM fails.

        Returns:
          {
            "category": str | None,
            "terms":    list[str],
            "brand":    str | None,
            "intent":   str,
          }
        """
        if not query or not query.strip():
            return {"category": None, "terms": [], "brand": None, "intent": ""}

        try:
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",   # fast + smart, great Arabic
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user",   "content": query.strip()},
                ],
                max_tokens=200,
                temperature=0.1,   # low temperature = consistent structured output
            )

            raw = response.choices[0].message.content.strip()

            # Strip accidental markdown code fences
            raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`")

            parsed = json.loads(raw)

            # Validate / sanitise
            category = parsed.get("category")
            if category and category.lower() not in VALID_CATEGORIES:
                category = None

            terms = [str(t).lower().strip() for t in parsed.get("terms", []) if t]
            brand = parsed.get("brand") or None
            intent = parsed.get("intent", query)

            logger.info(
                f"[QU] '{query}' → category={category}, "
                f"terms={terms}, brand={brand}"
            )
            return {
                "category": category,
                "terms":    terms,
                "brand":    brand,
                "intent":   intent,
            }

        except json.JSONDecodeError as exc:
            logger.warning(f"[QU] JSON parse error for '{query}': {exc} | raw={raw!r}")
        except Exception as exc:
            logger.warning(f"[QU] LLM call failed for '{query}': {exc}")

        # ── Fallback: basic tokenization (no LLM) ────────────────────────────
        return {
            "category": None,
            "terms":    [t for t in query.lower().split() if len(t) > 1],
            "brand":    None,
            "intent":   query,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
_qu: Optional[QueryUnderstanding] = None


def get_query_understanding() -> QueryUnderstanding:
    global _qu
    if _qu is None:
        _qu = QueryUnderstanding()
    return _qu