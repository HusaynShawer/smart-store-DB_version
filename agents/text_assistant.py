# agents/text_assistant.py
import asyncio
from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from sqlalchemy import select

from config.settings import get_settings
from config.database import AsyncSessionFactory, SessionModel, SearchLogModel
from agents.product_service import ProductService
from agents.backend_service import BackendService
from agents.location_service import resolve_location, sort_stores_by_distance

settings = get_settings()


def _detect_language(text: str) -> str:
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return "Arabic" if arabic > len(text) * 0.2 else "English"


_PROMPT = """
You are a smart shopping assistant for Zaki Store (متجر زكي).
You help customers find products across ALL registered merchants in Egypt.

⚠️ LANGUAGE RULE: Reply ONLY in {language}. Every single word.

RULES:
1. Always reply in {language}.
2. Use chat history for context — "ده", "الأول", "this one" = previously mentioned item.

3. PURCHASE FLOW:
   STEP 1: User mentions product → use search_products
   STEP 2: Show results clearly → ask which one
   STEP 3: User confirms → use place_order
   ❌ NEVER call place_order without confirmed product

4. AFTER SEARCH RESULTS:
   - Results are already in the Observation
   - Go directly to: Thought: I now know → Final Answer
   - NEVER repeat same search

5. LOCATION FLOW:
   User mentions city/governorate WITH product → use find_nearby_stores
   Format: 'product | location'  e.g. 'phone | قنا'

6. PRICE COMPARISON:
   If user asks "أرخص" or "compare" → search_products then show sorted by price

7. ORDER HISTORY:
   If user asks about their orders → use get_order_history

8. Multi-product: comma-separated → 'laptop, phone'
9. Greeting → greet back warmly

Previous conversation:
{chat_history}

Available tools:
{tools}

Use EXACTLY this format:
Question: the input
Thought: think about what to do
Action: tool name from [{tool_names}]
Action Input: tool input
Observation: tool result
Thought: I now know the answer
Final Answer: your natural friendly reply in {language}

Question: {input}
{agent_scratchpad}
"""


async def _direct_reply(x: str) -> str:
    return x


async def _place_order_stub(q: str) -> str:
    return "User confirmed purchase. Ask for name and phone if not already provided."


class TextAssistant:

    def __init__(self):
        self._store   = ProductService()
        self._backend = BackendService()

    async def process(
        self,
        message:          str,
        session_id:       str   = None,
        customer_name:    str   = None,
        customer_phone:   str   = None,
        selected_product: dict  = None,
        location_text:    str   = None,
        latitude:         float = None,
        longitude:        float = None,
    ) -> dict:

        if selected_product and selected_product.get("id"):
            return await self._handle_purchase(customer_name, customer_phone, selected_product)

        language        = _detect_language(message)
        request_products: list = []

        enriched = message
        if location_text:
            enriched = f"{message} [user_location: {location_text}]"
        elif latitude and longitude:
            enriched = f"{message} [user_gps: {latitude},{longitude}]"

        history = await self._get_history(session_id)

        try:
            executor = self._build_executor(
                request_products, latitude, longitude, language,
                customer_phone=customer_phone,
            )
            result = await executor.ainvoke({
                "input":        enriched,
                "chat_history": history,
                "language":     language,
            })
            output = result.get("output", "")
            await self._save_to_history(session_id, message, output)

            products = request_products[:6]
            return {
                "response":           output,
                "state":              "product_found" if products else "searching",
                "products":           products or None,
                "order_confirmation": None,
                "nearby_stores":      None,
            }

        except Exception as exc:
            return {
                "response":           f"عذراً، حدث خطأ: {exc}",
                "state":              "searching",
                "products":           None,
                "order_confirmation": None,
                "nearby_stores":      None,
            }

    # ── History ───────────────────────────────────────────────────────────────

    async def _get_history(self, session_id: str) -> str:
        if not session_id:
            return "No previous conversation."
        async with AsyncSessionFactory() as db:
            stmt   = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await db.execute(stmt)
            row    = result.scalar_one_or_none()
            if not row or not row.messages:
                return "No previous conversation."
            lines = []
            for msg in row.messages[-10:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                lines.append(f"{role}: {msg['content']}")
            return "\n".join(lines)

    async def _save_to_history(self, session_id: str, user_msg: str, assistant_msg: str):
        if not session_id:
            return
        async with AsyncSessionFactory() as db:
            stmt   = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await db.execute(stmt)
            row    = result.scalar_one_or_none()
            new_msgs = [
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ]
            if row:
                existing        = list(row.messages or [])
                existing.extend(new_msgs)
                row.messages    = existing[-20:]
                row.updated_at  = datetime.now(timezone.utc)
            else:
                row = SessionModel(
                    session_id=session_id,
                    messages=new_msgs,
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(row)
            await db.commit()

    # ── Log Search ────────────────────────────────────────────────────────────

    async def _log_search(self, query: str, count: int, customer_phone: str = None, gov: str = None):
        try:
            async with AsyncSessionFactory() as db:
                db.add(SearchLogModel(
                    query=query,
                    governorate=gov,
                    results_count=count,
                    customer_phone=customer_phone,
                ))
                await db.commit()
        except Exception:
            pass  # analytics لا تأثر على الـ flow الأساسي

    # ── Purchase ──────────────────────────────────────────────────────────────

    async def _handle_purchase(self, customer_name, customer_phone, selected_product) -> dict:
        if not customer_name or not customer_phone:
            return {
                "response": (
                    "تمام! عشان نكمل الطلب محتاج منك:\n"
                    "• اسمك الكامل\n"
                    "• رقم تليفونك\n\n"
                    "بعتهم وأنا هتواصل مع التاجر فوراً!"
                ),
                "state": "awaiting_confirm",
                "products": None, "order_confirmation": None, "nearby_stores": None,
            }

        product_name  = selected_product.get("title",    "")
        product_price = selected_product.get("price",    0)
        vendor_phone  = selected_product.get("shop_phone")
        shop_id       = selected_product.get("shop_id")
        shop_name     = selected_product.get("shop_name", "")

        # Fallback: دور على المتجر لو مش موجود
        if not shop_id or not vendor_phone:
            stores = await self._backend.get_stores_for_product(selected_product)
            if stores:
                shop_id      = shop_id      or stores[0]["id"]
                vendor_phone = vendor_phone or stores[0].get("phone", "")
                shop_name    = shop_name    or stores[0].get("name", "")

        result = await self._backend.send_order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            product_id=selected_product.get("id", "unknown"),
            product_name=product_name,
            product_price=product_price,
            shop_id=shop_id,
            vendor_phone=vendor_phone,
        )

        if result.get("success"):
            return {
                "response": (
                    f"✅ تم إرسال طلبك بنجاح!\n\n"
                    f"📦 {product_name}\n"
                    f"💰 {product_price} جنيه\n"
                    f"🏪 {shop_name}\n\n"
                    f"التاجر هيتواصل معك على {customer_phone} قريباً 🙏"
                ),
                "state": "order_sent",
                "products": None,
                "order_confirmation": result.get("data"),
                "nearby_stores": None,
            }
        return {
            "response": "عذراً، حصل خطأ في إرسال الطلب. حاول تاني بعد شوية 🙏",
            "state": "product_found",
            "products": None, "order_confirmation": None, "nearby_stores": None,
        }

    # ── Build Agent ───────────────────────────────────────────────────────────

    def _build_executor(
        self,
        request_products: list,
        user_lat:         float = None,
        user_lon:         float = None,
        language:         str   = "Arabic",
        customer_phone:   str   = None,
    ) -> AgentExecutor:

        # ──────────────────────────────────────────────────────────────────────
        async def search_and_summarize(query: str) -> str:
            sub_queries = [
                q.strip()
                for q in query.replace(" and ", ",").replace(" و ", ",").split(",")
                if q.strip()
            ]
            results = await asyncio.gather(
                *[self._store.search(q) for q in sub_queries],
                return_exceptions=True,
            )
            all_lines = []
            for sub_q, products in zip(sub_queries, results):
                if isinstance(products, Exception) or not products:
                    all_lines.append(f"\n❌ مفيش منتجات لـ '{sub_q}'.")
                    continue

                products = products[:5]
                all_lines.append(f"\n🔍 نتائج '{sub_q}' ({len(products)} منتج):\n")

                # ✅ FIX: لكل منتج بنجيب متاجره الصح (مش بالـ index)
                for i, p in enumerate(products, 1):
                    stores   = await self._backend.get_stores_for_product(p)
                    enriched = dict(p)

                    if stores:
                        # نعرض كل المتاجر المتاحة لهذا المنتج
                        enriched.update({
                            "shop_id":          stores[0]["id"],
                            "shop_name":        stores[0]["name"],
                            "shop_governorate": stores[0].get("governorate", ""),
                            "shop_phone":       stores[0].get("phone", ""),
                            "all_stores":       stores,
                        })

                    request_products.append(enriched)

                    stores_summary = " | ".join(
                        f"🏪 {s['name']} ({s['governorate']})"
                        for s in stores[:3]
                    ) if stores else "متاح"

                    all_lines.append(
                        f"  {i}. {p['title']}\n"
                        f"     💰 {p['price']} جنيه | 📂 {p['category']}\n"
                        f"     {stores_summary}\n"
                    )

                # ✅ جديد: حفظ بحث في analytics
                asyncio.create_task(
                    self._log_search(sub_q, len(products), customer_phone)
                )

            all_lines.append(f"\nReply in {language}, show results clearly, ask which one they want.")
            return "\n".join(all_lines)

        # ──────────────────────────────────────────────────────────────────────
        async def find_nearby_stores(query: str) -> str:
            parts   = query.split("|")
            product = parts[0].strip()
            loc     = parts[1].strip() if len(parts) > 1 else ""

            lat, lon = user_lat, user_lon
            if not lat and loc:
                coords = resolve_location(loc)
                if coords:
                    lat, lon = coords

            if not lat:
                return "مش قادر أحدد موقعك. قولي اسم محافظتك أو مدينتك."

            products_res, stores_res = await asyncio.gather(
                self._store.search(product),
                self._backend.get_stores_by_product(product),
                return_exceptions=True,
            )

            products = products_res[:5] if not isinstance(products_res, Exception) else []
            stores   = stores_res       if not isinstance(stores_res,   Exception) else []
            sorted_stores = sort_stores_by_distance(stores, lat, lon) if stores else []

            if not products:
                if not sorted_stores:
                    return f"مفيش منتجات أو متاجر لـ '{product}'."
                lines = [f"مفيش '{product}' في DB حالياً، لكن أقرب المتاجر:\n"]
                for i, s in enumerate(sorted_stores[:5], 1):
                    lines.append(
                        f"  {i}. 🏪 {s['name']} — {s['governorate']}\n"
                        f"     📏 {s.get('distance_km', '?')} كم | 📞 {s.get('phone', '')}"
                    )
                lines.append(f"\nTell user in {language} these are closest stores. Suggest calling.")
                return "\n".join(lines)

            lines = [f"🔍 نتائج '{product}' مرتبة بالقرب من {loc}:\n"]
            for i, p in enumerate(products, 1):
                # ✅ FIX: اجيب المتاجر الفعلية للمنتج ده
                p_stores   = await self._backend.get_stores_for_product(p)
                p_sorted   = sort_stores_by_distance(p_stores, lat, lon) if p_stores else []
                enriched   = dict(p)

                if p_sorted:
                    best = p_sorted[0]
                    enriched.update({
                        "shop_id":          best["id"],
                        "shop_name":        best["name"],
                        "shop_governorate": best["governorate"],
                        "shop_distance":    best.get("distance_km", "?"),
                        "shop_phone":       best.get("phone", ""),
                    })
                request_products.append(enriched)

                store_info = (
                    f"🏪 {enriched.get('shop_name', '?')} — "
                    f"{enriched.get('shop_governorate', '?')} "
                    f"({enriched.get('shop_distance', '?')} كم) | "
                    f"📞 {enriched.get('shop_phone', '')}"
                    if p_sorted else "متاح"
                )
                lines.append(
                    f"  {i}. {p['title']}\n"
                    f"     💰 {p['price']} جنيه\n"
                    f"     {store_info}\n"
                )

            lines.append(f"\nShow in {language} sorted by distance. Ask which one they want.")
            return "\n".join(lines)

        # ──────────────────────────────────────────────────────────────────────
        async def get_order_history(phone: str) -> str:
            """يجيب سجل طلبات العميل."""
            from sqlalchemy import select
            from config.database import OrderModel
            clean = phone.strip().replace(" ", "")
            async with AsyncSessionFactory() as db:
                stmt   = select(OrderModel).where(
                    OrderModel.customer_phone.like(f"%{clean[-8:]}%")
                ).order_by(OrderModel.created_at.desc()).limit(5)
                result = await db.execute(stmt)
                rows   = result.scalars().all()

            if not rows:
                return f"مفيش طلبات سابقة لهذا الرقم."

            lines = ["📋 آخر طلباتك:\n"]
            for r in rows:
                lines.append(
                    f"• #{r.id} — {r.product_name} — {r.product_price} جنيه\n"
                    f"  الحالة: {r.status} | {str(r.created_at)[:10]}"
                )
            return "\n".join(lines)

        # ──────────────────────────────────────────────────────────────────────
        async def browse_category(category: str) -> str:
            products = (await self._store.by_category(category))[:5]
            if not products:
                return f"مفيش منتجات في كاتيجوري: {category}"
            lines = [f"منتجات {category}:\n"]
            for i, p in enumerate(products, 1):
                stores   = await self._backend.get_stores_for_product(p)
                enriched = dict(p)
                if stores:
                    enriched.update({
                        "shop_id":    stores[0]["id"],
                        "shop_name":  stores[0]["name"],
                        "shop_phone": stores[0].get("phone", ""),
                    })
                request_products.append(enriched)
                lines.append(f"{i}. {p['title']} | {p['price']} جنيه | ID: {p['id']}")
            lines.append(f"\nReply in {language} and ask which one they want.")
            return "\n".join(lines)

        # ── Tools ─────────────────────────────────────────────────────────────
        tools = [
            Tool.from_function(
                name="direct_reply",
                func=lambda x: x, coroutine=_direct_reply,
                description="تحيات، وداع، محادثة عامة.",
            ),
            Tool.from_function(
                name="search_products",
                func=lambda q: q, coroutine=search_and_summarize,
                description="ابحث عن منتجات بالعربي أو الإنجليزي. متعدد: 'laptop, phone'. استخدمه لما مفيش مدينة.",
            ),
            Tool.from_function(
                name="get_by_category",
                func=lambda c: c, coroutine=browse_category,
                description="جيب منتجات بالكاتيجوري: electronics, jewelery, men's clothing, women's clothing.",
            ),
            Tool.from_function(
                name="find_nearby_stores",
                func=lambda q: q, coroutine=find_nearby_stores,
                description="ابحث عن منتجات قريبة من موقع. Format: 'product | location' مثال: 'phone | قنا'.",
            ),
            Tool.from_function(
                name="get_order_history",
                func=lambda p: p, coroutine=get_order_history,
                description="جيب سجل طلبات العميل. Input: رقم التليفون.",
            ),
            Tool.from_function(
                name="place_order",
                func=lambda q: "Ask for customer details.",
                coroutine=_place_order_stub,
                description="استخدمه فقط لما العميل يأكد منتج بالضبط: 'هشتريه', 'الأول', 'the first one'.",
            ),
        ]

        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            google_api_key=settings.GEMINI_API_KEY,
        )

        agent = create_react_agent(
            llm=llm,
            tools=tools,
            prompt=PromptTemplate.from_template(_PROMPT),
        )

        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=settings.AGENT_VERBOSE,
            handle_parsing_errors=True,
            max_iterations=settings.AGENT_MAX_ITERATIONS,
            early_stopping_method="generate",
        )