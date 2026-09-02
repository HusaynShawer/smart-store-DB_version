# app/agents/nodes.py
"""
LangGraph nodes — pure-ish functions that transform AgentState.

Dependencies (DB session, services, LLM) are injected via closures built in
`graph.build_graph(session)` so nodes stay testable and decoupled from FastAPI.
"""
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.prompts import RESPOND_SYSTEM
from app.agents.state import AgentState
from app.core.llm import ChatLLM
from app.core.logging import get_logger
from app.db.repositories.session import SessionRepository
from app.services.location_service import resolve_location, sort_stores_by_distance
from app.services.order_service import OrderService
from app.services.search_service import SearchService

logger = get_logger(__name__)

_GREET_WORDS = (
    "مرحبا", "مرحب", "اهلا", "أهلا", "السلام", "هاي", "صباح", "مساء",
    "hello", "hi", "hey", "good morning", "good evening", "bye", "باي", "وداع",
)
_PURCHASE_WORDS = (
    "هشتريه", "هشتري", "اشتري", "اشتريه", "اطلب", "اطلبه", "هطلب", "شراء",
    "buy", "purchase", "preorder", "اطلب المنتج", "تأكيد الطلب",
)
_CATEGORY_WORDS = (
    "تصنيف", "اقسام", "أقسام", "categories", "category", "براوز",
    "إلكترونيات", "الكترونيات", "ملابس", "مجوهرات", "جواهر", "عطور", "إكسسورات",
)
_NEARBY_WORDS = ("قريب", "الأقرب", "اقرب", "أقرب", "فين", "وين", "near", "closest", "قريبة من")


def detect_language(text: str) -> str:
    """Cheap Arabic/English detection based on Unicode range density."""
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return "Arabic" if arabic > len(text) * 0.2 else "English"


def _keyword_intent(text: str) -> str:
    """Deterministic fallback classifier used when the LLM router fails."""
    lowered = text.lower().strip()
    if any(w in lowered for w in _GREET_WORDS) and len(lowered) <= 30:
        return "greet"
    if any(w in lowered for w in _PURCHASE_WORDS):
        return "purchase"
    if any(w in lowered for w in _NEARBY_WORDS):
        return "nearby"
    if any(w in lowered for w in _CATEGORY_WORDS):
        return "category"
    return "search"


def _format_products(products: list[dict]) -> str:
    if not products:
        return "(none)"
    lines = []
    for p in products:
        store = f" | store: {p.get('shop_name')} ({p.get('shop_phone', '')})" if p.get("shop_name") else ""
        lines.append(
            f"- id={p['id']}: {p['title']} | ${p['price']} "
            f"| category: {p.get('category', '')}{store}"
        )
    return "\n".join(lines)


def _format_stores(stores: list[dict]) -> str:
    if not stores:
        return "(none)"
    return "\n".join(
        f"- {s.get('name')} | {s.get('governorate')} | "
        f"{s.get('distance_km', '?')} km | {s.get('phone', '')}"
        for s in stores
    )


VISION_RE = re.compile(r"\[Product image identified as:\s*([^\]]+)\]")


class AgentNodes:
    """Factory of LangGraph node functions bound to a request's dependencies."""

    def __init__(self, session: AsyncSession, llm: ChatLLM) -> None:
        self._session = session
        self._llm = llm
        self._search = SearchService(session)
        self._orders = OrderService(session)
        self._sessions = SessionRepository(session)

    # ── Nodes ────────────────────────────────────────────────────────────────

    @staticmethod
    def _clean_input(text: str) -> str:
        """Strip the vision marker so routing/search get only the user's words."""
        return VISION_RE.sub("", text).strip()

    async def load_context(self, state: AgentState) -> dict:
        vision_context = None

        current = state.get("input", "")
        match = VISION_RE.search(current)
        if match:
            vision_context = match.group(1).strip()

        session_id = state.get("session_id")
        if not session_id:
            return {
                "chat_history": "No previous conversation.",
                "vision_context": vision_context,
            }
        messages = await self._sessions.get_messages(session_id, limit=10)
        if not messages:
            return {
                "chat_history": "No previous conversation.",
                "vision_context": vision_context,
            }
        lines = [
            f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')}"
            for m in messages
        ]
        history = "\n".join(lines)

        found = VISION_RE.search(history)
        if found and not vision_context:
            vision_context = found.group(1).strip()
        return {"chat_history": history, "vision_context": vision_context}

    async def route_intent(self, state: AgentState) -> dict:
        text = self._clean_input(state.get("input", ""))
        language = detect_language(text)
        vision = state.get("vision_context")
        # Give the router the visual context so a price/buy question about an
        # uploaded image ("عايز سعر الموبايل ده") routes to search, not purchase.
        routing_text = text
        if vision:
            routing_text = f"{text} [uploaded image shows: {vision}]".strip()
        intent = await self._classify_intent(routing_text)
        return {"language": language, "intent": intent}

    async def _classify_intent(self, text: str) -> str:
        from app.agents.prompts import INTENTS, ROUTER_SYSTEM

        data = await self._llm.acomplete_json(ROUTER_SYSTEM, text)
        intent = (data or {}).get("intent") if isinstance(data, dict) else None
        if intent not in INTENTS:
            return _keyword_intent(text)
        return intent

    async def search_products(self, state: AgentState) -> dict:
        query = self._clean_input(state.get("input", ""))
        vision = state.get("vision_context")
        # Fuse the vision-detected product into the query so typed words like
        # "how much is this phone" still search for the product in the image.
        if vision:
            query = f"{query} {vision}".strip()
        if not query:
            query = state.get("input", "")
        products = await self._search.search(query)
        return {
            "products": products,
            "answer_state": "product_found" if products else "searching",
        }

    async def category_products(self, state: AgentState) -> dict:
        query = self._clean_input(state.get("input", ""))
        category = self._extract_category(query)
        if category:
            products = await self._search.by_category(category)
        else:
            # No explicit category keyword → let semantic search interpret the
            # query (e.g. "منتج ذهبي فاخر لهدية" → jewelry), then filter by the
            # dominant category of the top results to honour a "browse" intent.
            products = await self._search.search(query)
            cats = {p.get("category") for p in products[:4]}
            dominant = max(cats, key=lambda c: sum(1 for p in products if p.get("category") == c)) if cats else None
            if dominant:
                rows = await self._search.by_category(dominant)
                if rows:
                    products = rows
        return {
            "products": products,
            "answer_state": "product_found" if products else "searching",
        }

    def _extract_category(self, query: str) -> str | None:
        lowered = query.lower()
        for name in (
            "electronics", "electronic",
            "jewelery", "jewelry", "men's clothing",
            "women's clothing", "clothing", "beauty", "fragrances",
        ):
            if name in lowered:
                return name
        maps = {
            "إلكترونيات": "electronics", "الكترونيات": "electronics",
            "الالكترونيات": "electronics", "موبايلات": "electronics",
            "ملابس": "clothing", "الملابس": "clothing", "هدوم": "clothing",
            "مجوهرات": "jewelery", "جواهر": "jewelery", "المجوهرات": "jewelery",
            "حلي": "jewelery", "الحلي": "jewelery",
            "اكسسوارات": "jewelery", "اكسسورات": "jewelery",
            "عطور": "beauty", "تجميل": "beauty", "مكياج": "beauty",
            "رياضة": "sports", "ألعاب": "electronics", "العاب": "electronics",
            "ساعات": "watches", "كتب": "books", "منزل": "home",
        }
        for ar, en in maps.items():
            if ar in lowered:
                return en
        return None

    async def nearby_stores(self, state: AgentState) -> dict:
        query = state.get("input", "")
        lat, lon = state.get("latitude"), state.get("longitude")
        location_text = state.get("location_text") or self._extract_location_hint(query)
        if not lat and location_text:
            coords = resolve_location(location_text)
            if coords:
                lat, lon = coords

        if not lat or not lon:
            return {
                "response": "مش قادر أحدد موقعك. قولي اسم محافظتك أو مدينتك.",
                "answer_state": "conversation",
            }

        products = await self._search.search_nearby(query, lat, lon)
        stores = sort_stores_by_distance(
            await self._search_stores_for(query), lat, lon
        )
        return {
            "products": products,
            "nearby_stores": stores,
            "answer_state": "product_found" if products else "nearby",
        }

    async def _search_stores_for(self, query: str) -> list[dict]:
        from app.schemas.serializers import store_to_dict
        from app.services.search_service import translate

        rows = await self._sessions_store_rows(query)
        _ = translate  # keep search_service.translate as home of the map
        return [store_to_dict(r) for r in rows]

    async def _sessions_store_rows(self, query: str) -> list:
        from app.db.repositories.store import StoreRepository

        repo = StoreRepository(self._session)
        rows = await repo.get_stores_by_product(query)
        if not rows:
            rows = await repo.list()
        return rows

    def _extract_location_hint(self, text: str) -> str | None:
        for token in (
            "القاهرة", "الجيزة", "الإسكندرية", "الاسكندرية", "المنيا", "أسيوط",
            "اسيوط", "الأقصر", "الاقصر", "قنا", "سوهاج", "أسوان", "اسوان",
            "بورسعيد", "دمياط", "الفيوم", "الغربية", "الشرقية",
            "cairo", "qena", "luxor", "alex", "sohag", "asyut", "minya", "aswan",
        ):
            if token in text:
                return token
        return None

    async def place_order(self, state: AgentState) -> dict:
        selected = state.get("selected_product")
        if not selected or not selected.get("id"):
            return {
                "response": (
                    "تمام! عشان نكمل الشراء لسه محتاجين نشوفهيلك المنتج الأول. "
                    "لو شايف النتايج فوق اختار واحد منها وقولي رقمه."
                ),
                "answer_state": "conversation",
            }

        name, phone = state.get("customer_name"), state.get("customer_phone")
        if not name or not phone:
            return {
                "response": (
                    "تمام! عشان نكمل الطلب محتاج منك:\n"
                    "• اسمك\n• رقم تليفونك\n\n"
                    "بعتهم وأنا هدّي طلبك للمتجر فوراً!"
                ),
                "answer_state": "awaiting_confirm",
            }

        result = await self._orders.create_order(
            customer_name=name,
            customer_phone=phone,
            product_id=selected.get("id"),
            product_name=selected.get("title", ""),
            product_price=selected.get("price", 0),
            shop_id=selected.get("shop_id"),
            product_url=selected.get("product_url") or selected.get("image"),
            vendor_phone=selected.get("shop_phone"),
        )
        if not result.get("success"):
            return {
                "response": "عذراً، حصل خطأ في إرسال الطلب. حاول تاني بعد شوية 🙏",
                "answer_state": "product_found",
            }

        confirm = {
            "order_id": result["order_id"],
            "product_name": result["product_name"],
            "product_price": result["product_price"],
            "customer_name": result["customer_name"],
            "customer_phone": result["customer_phone"],
            "vendor_phone": result["vendor_phone"],
            "twilio_sent": result["twilio_sent"],
        }

        shop_parts = []
        if selected.get("shop_name"):
            shop_parts.append(
                f"المتجر: {selected['shop_name']} — {selected.get('shop_governorate', '')}"
            )
        link = self._orders.whatsapp_vendor_link(
            result["product_name"], result["product_price"],
            result["customer_name"], result["customer_phone"], result["vendor_phone"],
        )
        if link:
            shop_parts.append(
                f"📱 <a href='{link}' target='_blank' style='color: #4ade80;'>"
                "تواصل مع التاجر عبر واتساب</a>"
            )

        response = (
            "✅ تم إرسال طلبك بنجاح!\n\n"
            f"🛍️ المنتج: {result['product_name']}\n"
            f"💰 السعر: ${result['product_price']}\n"
            + (("\n".join(shop_parts) + "\n") if shop_parts else "")
            + f"\nصاحب المتجر هيتواصل معاك على {result['customer_phone']} قريباً 🙏"
        )
        return {
            "response": response,
            "order_confirmation": confirm,
            "answer_state": "order_sent",
        }

    async def respond(self, state: AgentState) -> dict:
        # Already answered (short-circuit from purchase / location-missing).
        if state.get("response"):
            return {}

        intent = state.get("intent", "chat")
        intent_label = {
            "greet": "greeting/conversation",
            "chat": "small talk / general question",
            "search": "product search",
            "category": "browsing a category",
            "nearby": "finding products near the user",
            "purchase": "completing a purchase",
        }.get(intent, intent)

        system = RESPOND_SYSTEM.format(
            language=state.get("language", "Arabic"),
            intent_label=intent_label,
            history=state.get("chat_history", "None"),
            products=_format_products(state.get("products") or []),
            nearby=_format_stores(state.get("nearby_stores") or []),
            order=state.get("order_confirmation") or "None",
            vision=state.get("vision_context") or "None",
        )
        answer = await self._llm.acomplete(system, state.get("input", ""))
        return {
            "response": answer,
            "answer_state": state.get("answer_state", "conversation"),
        }