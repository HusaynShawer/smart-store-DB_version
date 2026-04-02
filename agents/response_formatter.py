# agents/response_formatter.py
import random
from typing import Optional


class ResponseFormatter:
    """ردود جاهزة للتحيات والاستفسارات البسيطة — بدون LLM."""

    _GREETINGS = [
        "أهلاً وسهلاً!  أنا مساعدك الذكي في متجر زكي.\nعندنا آلاف المنتجات من إلكترونيات وملابس ومجوهرات وأكتر.\nقولي إيه اللي بتدور عليه وأنا هلاقيه لك! 🛍️",
        "مرحباً!  يسعدني أساعدك اليوم.\nمتجر زكي عنده كل حاجة — ابحث بأي كلمة وأنا هجيبلك أحسن النتايج.",
    ]

    _SERVICES = (
        "خدماتنا في متجر زكي:\n\n"
        " البحث عن المنتجات — قولي اسم أي منتج وأنا هدوّرك عليه\n"
        " تسهيل الشراء — لما تعجبك منتج بقول 'هشتريه' وأنا هتواصل مع المتجر عنك\n"
        " عرض التصنيفات — إلكترونيات، ملابس، مجوهرات وأكتر\n\n"
        "إيه اللي تحب تبدأ بيه؟ "
    )

    _FAREWELLS = [
        "مع السلامة! أتمنالك يوم سعيد.",
        "إلى اللقاء! لا تتردد ترجع لو محتاج أي حاجة ",
    ]

    def handle_general_query(self, message: str) -> Optional[str]:
        """
        لو الرسالة تحية أو استفسار → رجّع رد جاهز.
        لو لأ → رجّع None (معناها الـ Agent يشتغل).
        """
        m = message.lower().strip()

        if any(w in m for w in ["مرحب", "السلام", "هاي", "hi", "hello", "أهلاً", "اهلا", "صباح", "مساء"]):
            return random.choice(self._GREETINGS)

        if any(w in m for w in ["خدمات", "بتعمل إيه", "بتعمل ايه", "تقدر تعمل", "تعمل ايه", "what can", "help"]):
            return self._SERVICES

        if any(w in m for w in ["من أنت", "من انت", "who are you", "مين أنت"]):
            return (
                "أنا مساعد متجر زكي الذكي \n"
                "بساعدك تبحث عن منتجات وتتواصل مع المتاجر بسهولة."
            )

        if any(w in m for w in ["مع السلامة", "باي", "bye", "goodbye", "وداعاً"]):
            return random.choice(self._FAREWELLS)

        return None