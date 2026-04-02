# agents/text_assistant.py
import asyncio
from datetime import datetime, timezone

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from sqlalchemy import select

from config.settings import get_settings
from config.database import AsyncSessionFactory, SessionModel
from agents.product_service import ProductService
from agents.backend_service import BackendService
from agents.location_service import resolve_location, sort_stores_by_distance

settings = get_settings()


def _detect_language(text: str) -> str:
    """Detect if message is Arabic or English."""
    arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
    return "Arabic" if arabic_chars > len(text) * 0.2 else "English"


_PROMPT = """
You are a smart shopping assistant for Zaki Store (متجر زكي).

⚠️ LANGUAGE INSTRUCTION: You MUST reply in {language} ONLY. No exceptions.

RULES:
1. ALWAYS reply in {language} — every single word of your response
2. Use chat history to understand context and references like "this one", "the first", "ده", "هشتريه"

3. PURCHASE FLOW:
   STEP 1: User mentions product → search_products first
   STEP 2: Show results → ask which one they want
   STEP 3: User confirms specific product → use place_order
   NEVER call place_order without a specific product chosen first

4. AFTER GETTING SEARCH RESULTS:
   - You ALREADY have the results in the Observation
   - Go DIRECTLY to: Thought: I now know → Final Answer
   - NEVER search again for the same query
   - NEVER repeat an Action you already did

5. LOCATION FLOW:
   If user mentions a governorate/city WITH a product → use find_nearby_stores
   Input format: 'product | location'  →  'phone | قنا'

6. MULTI-PRODUCT: use comma → 'laptop, phone'
7. If user greets → greet back warmly in {language}

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


async def _place_order_response(query: str) -> str:
    return "User wants to purchase. Ask for name and phone if not provided."


class TextAssistant:

    def __init__(self):
        self._store   = ProductService()
        self._backend = BackendService()

    async def process(
        self,
        message: str,
        session_id: str = None,
        customer_name: str = None,
        customer_phone: str = None,
        selected_product: dict = None,
        location_text: str = None,
        latitude: float = None,
        longitude: float = None,
    ) -> dict:

        if selected_product and selected_product.get("id"):
            return await self._handle_purchase(customer_name, customer_phone, selected_product)

        request_products: list = []

        # Detect language from user message
        language = _detect_language(message)

        enriched_message = message
        if location_text:
            enriched_message = f"{message} [user_location: {location_text}]"
        elif latitude and longitude:
            enriched_message = f"{message} [user_gps: {latitude},{longitude}]"

        history = await self._get_history(session_id)

        try:
            executor = self._build_executor(request_products, latitude, longitude, language)
            result = await executor.ainvoke({
                "input":        enriched_message,
                "chat_history": history,
                "language":     language,
            })
            output = result.get("output", "")
            await self._save_to_history(session_id, message, output)

            products = request_products[:6]
            return {
                "response": output,
                "state": "product_found" if products else "searching",
                "products": products or None,
                "order_confirmation": None,
                "nearby_stores": None,
            }

        except Exception as exc:
            return {
                "response": f"عذراً، حدث خطأ: {exc}",
                "state": "searching",
                "products": None,
                "order_confirmation": None,
                "nearby_stores": None,
            }

    async def _get_history(self, session_id: str) -> str:
        if not session_id:
            return "No previous conversation."
        async with AsyncSessionFactory() as db:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()
            if not row or not row.messages:
                return "No previous conversation."
            messages = row.messages[-10:]
            lines = []
            for msg in messages:
                role = "User" if msg["role"] == "user" else "Assistant"
                lines.append(f"{role}: {msg['content']}")
            return "\n".join(lines)

    async def _save_to_history(self, session_id: str, user_msg: str, assistant_msg: str):
        if not session_id:
            return
        async with AsyncSessionFactory() as db:
            stmt = select(SessionModel).where(SessionModel.session_id == session_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()

            new_messages = [
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": assistant_msg},
            ]

            if row:
                existing = list(row.messages or [])
                existing.extend(new_messages)
                row.messages   = existing[-20:]
                row.updated_at = datetime.now(timezone.utc)
            else:
                row = SessionModel(
                    session_id=session_id,
                    messages=new_messages,
                    updated_at=datetime.now(timezone.utc),
                )
                db.add(row)

            await db.commit()

    async def _handle_purchase(self, customer_name, customer_phone, selected_product) -> dict:
        if not customer_name or not customer_phone:
            return {
                "response": (
                    "تمام! عشان نكمل الطلب محتاج منك:\n"
                    "• اسمك\n• رقم تليفونك\n\n"
                    "بعتهم وأنا هتواصل مع المتجر فوراً!"
                ),
                "state": "awaiting_confirm",
                "products": None,
                "order_confirmation": None,
                "nearby_stores": None,
            }

        product_url = (
            selected_product.get("product_url")
            or selected_product.get("image")
            or f"https://store.zaki.com/products/{selected_product.get('id')}"
        )

        # Get full product details from DB to ensure we have all data
        full_product = None
        if selected_product.get("id"):
            full_product = await self._store.get_product_by_id(selected_product.get("id"))

        product_name  = full_product.get("title") if full_product else selected_product.get("title", "")
        product_price = full_product.get("price") if full_product else selected_product.get("price", 0)
        product_image = full_product.get("image") if full_product else selected_product.get("image", "")
        vendor_phone  = selected_product.get("shop_phone")
        shop_id       = selected_product.get("shop_id")

        # FIX: If shop_id or vendor_phone is missing, look it up from stores table
        if not shop_id or not vendor_phone:
            print(f"⚠️  shop_id or vendor_phone missing — looking up store for: {product_name}")
            stores = await self._backend.get_stores_by_product(product_name)
            if stores:
                shop_id      = shop_id      or stores[0]["id"]
                vendor_phone = vendor_phone or stores[0].get("phone", "")
                print(f" Found store: id={shop_id}, phone={vendor_phone}")
            else:
                print(f" No store found for product: {product_name}")

        result = await self._backend.send_order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            product_id=selected_product.get("id", "unknown"),
            product_name=product_name,
            product_price=product_price,
            shop_id=shop_id,
            product_url=product_url,
            vendor_phone=vendor_phone,
        )

        if result.get("success"):
            shop_info = ""
            if selected_product.get("shop_name"):
                shop_info = (
                    f" المتجر: {selected_product['shop_name']} "
                    f"— {selected_product.get('shop_governorate','')}\n"
                )

            # Create WhatsApp link for this specific vendor
            if vendor_phone:
                clean_phone = ''.join(filter(str.isdigit, vendor_phone))
                if clean_phone.startswith('0'):
                    clean_phone = '2' + clean_phone  # Egypt country code
                whatsapp_message = (
                    f"مرحباً، لدي طلب من متجر زكي%0A%0A"
                    f"المنتج: {product_name}%0A"
                    f"السعر: ${product_price}%0A"
                    f"العميل: {customer_name}%0A"
                    f"رقم العميل: {customer_phone}"
                )
                whatsapp_link = f"https://wa.me/{clean_phone}?text={whatsapp_message}"
                shop_info += f"📱 <a href='{whatsapp_link}' target='_blank' style='color: #4ade80;'>تواصل مع التاجر عبر واتساب</a>\n"

            return {
                "response": (
                    f" تم إرسال طلبك بنجاح!\n\n"
                    f" المنتج: {product_name}\n"
                    f" السعر: ${product_price}\n"
                    f"{shop_info}"
                    f"\nصاحب المتجر هيتواصل معاك على {customer_phone} قريباً 🙏"
                ),
                "state": "order_sent",
                "products": None,
                "order_confirmation": result.get("data"),
                "nearby_stores": None,
            }
        return {
            "response": "عذراً، حصل خطأ في إرسال الطلب. حاول تاني بعد شوية 🙏",
            "state": "product_found",
            "products": None,
            "order_confirmation": None,
            "nearby_stores": None,
        }

    def _build_executor(self, request_products, user_lat=None, user_lon=None, language="Arabic") -> AgentExecutor:

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
            for sub_query, products in zip(sub_queries, results):
                if isinstance(products, Exception) or not products:
                    all_lines.append(f"\n No products found for '{sub_query}'.")
                    continue

                products = products[:5]

                # ✅ FIX: Get store data for each product
                stores_result = await self._backend.get_stores_by_product(sub_query)
                stores = stores_result if not isinstance(stores_result, Exception) and stores_result else []

                all_lines.append(f"\n🔍 Results for '{sub_query}' ({len(products)} found):")
                for i, p in enumerate(products, 1):
                    # ✅ FIX: Enrich product with shop data
                    enriched = dict(p)
                    if stores:
                        store = stores[i - 1] if (i - 1) < len(stores) else stores[0]
                        enriched.update({
                            "shop_id":          store["id"],
                            "shop_name":        store["name"],
                            "shop_governorate": store.get("governorate", ""),
                            "shop_phone":       store.get("phone", ""),
                        })
                        print(f" Enriched product '{p['title']}' with shop: {store['name']} | {store.get('phone','')}")

                    #  FIX: append enriched instead of p
                    request_products.append(enriched)

                    shop_info = (
                        f"| {enriched.get('shop_name','?')} "
                        f"| {enriched.get('shop_phone','')}"
                        if stores else ""
                    )
                    all_lines.append(
                        f"  {i}. {p['title']} | Price: ${p['price']} "
                        f"| Category: {p['category']} | ID: {p['id']} {shop_info}"
                    )

            if not all_lines:
                return "No products found."
            all_lines.append(f"\nReply naturally in {language}, show results grouped, ask which one(s) they want.")
            return "\n".join(all_lines)

        async def browse_category(category: str) -> str:
            products = (await self._store.by_category(category))[:5]
            if not products:
                return f"No products found in category: {category}"

            # FIX: Enrich with shop data
            stores_result = await self._backend.get_stores_by_product(category)
            stores = stores_result if stores_result else []

            lines = [f"Products in {category}:"]
            for i, p in enumerate(products, 1):
                enriched = dict(p)
                if stores:
                    store = stores[i - 1] if (i - 1) < len(stores) else stores[0]
                    enriched.update({
                        "shop_id":    store["id"],
                        "shop_name":  store["name"],
                        "shop_phone": store.get("phone", ""),
                    })
                request_products.append(enriched)
                lines.append(f"{i}. {p['title']} | Price: ${p['price']} | ID: {p['id']}")

            lines.append(f"\nReply naturally in {language} and ask which one they want.")
            return "\n".join(lines)

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

            products_result, stores_result = await asyncio.gather(
                self._store.search(product),
                self._backend.get_stores_by_product(product),
                return_exceptions=True,
            )

            products = products_result[:5] if not isinstance(products_result, Exception) else []
            stores   = stores_result       if not isinstance(stores_result, Exception) else []
            all_stores_sorted = sort_stores_by_distance(stores, lat, lon) if stores else []

            if not products:
                if not all_stores_sorted:
                    return f"No products or stores found for '{product}'."
                lines = [f"No '{product}' in DB right now. Here are the nearest stores:\n"]
                for i, store in enumerate(all_stores_sorted[:5], 1):
                    lines.append(
                        f"  {i}. 🏪 {store['name']} — {store['governorate']}\n"
                        f"     📏 {store.get('distance_km', '?')} km |  {store.get('phone', '')}"
                    )
                lines.append(f"\nTell user in {language} these are nearest stores sorted by distance. Suggest calling to check availability.")
                return "\n".join(lines)

            lines = [f"🔍 Found {len(products)} products near {loc}:\n"]
            for i, p in enumerate(products):
                store = (
                    all_stores_sorted[i] if i < len(all_stores_sorted)
                    else (all_stores_sorted[0] if all_stores_sorted else None)
                )
                enriched = dict(p)
                if store:
                    enriched.update({
                        "shop_id":          store["id"],
                        "shop_name":        store["name"],
                        "shop_governorate": store["governorate"],
                        "shop_distance":    store.get("distance_km", "?"),
                        "shop_phone":       store.get("phone", ""),
                    })
                request_products.append(enriched)
                store_info = (
                    f"🏪 {enriched.get('shop_name','?')} — "
                    f"{enriched.get('shop_governorate','?')} "
                    f"({enriched.get('shop_distance','?')} كم) | "
                    f"📞 {enriched.get('shop_phone','')}"
                    if store else ""
                )
                lines.append(f"  {i+1}. {p['title']} | ${p['price']} | {store_info}")

            lines.append(f"\nShow in {language} products with store info sorted by distance. Ask which one they want.")
            return "\n".join(lines)

        tools = [
            Tool.from_function(name="direct_reply",       func=lambda x: x, coroutine=_direct_reply,           description="Use for greetings, farewells, general conversation."),
            Tool.from_function(name="search_products",    func=lambda q: q, coroutine=search_and_summarize,     description="Search products in Arabic or English. Multiple: 'laptop, phone'. Use when NO location mentioned."),
            Tool.from_function(name="get_by_category",    func=lambda c: c, coroutine=browse_category,          description="Get products by category: electronics, jewelery, men's clothing, women's clothing."),
            Tool.from_function(name="find_nearby_stores", func=lambda q: q, coroutine=find_nearby_stores,       description="Find products near user location. Input: 'product | location' → 'phone | قنا'."),
            Tool.from_function(name="place_order",        func=lambda q: "Ask for customer details.", coroutine=_place_order_response, description="Use ONLY when user confirms a specific product: 'هشتريه', 'the first one'."),
        ]

        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            google_api_key=settings.GEMINI_API_KEY,
        )

        prompt = PromptTemplate.from_template(_PROMPT)

        agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)

        return AgentExecutor(
            agent=agent, tools=tools,
            verbose=settings.AGENT_VERBOSE,
            handle_parsing_errors=True,
            max_iterations=settings.AGENT_MAX_ITERATIONS,
            early_stopping_method="generate",
        )