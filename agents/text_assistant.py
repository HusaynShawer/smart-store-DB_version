# agents/text_assistant.py
import asyncio
import logging
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
logger = logging.getLogger(__name__)


def _detect_language(text: str) -> str:
    """Detect if text is primarily Arabic or English."""
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
    return "Arabic" if arabic > len(text) * 0.2 else "English"


_PROMPT = """
You are a professional shopping assistant for Zaki Store.
You help customers find products across all registered merchants in Egypt.

LANGUAGE RULE: Reply ONLY in {language}. Every single word must be in {language}.

RULES:
1. Always reply in {language}.
2. Use chat history for context - reference previously mentioned items.

3. SEARCH RULES — CRITICAL:
   - Call search_products ONCE per product per conversation turn.
   - If the Observation contains "FINAL RESULT: No products found" — stop immediately.
     Do NOT call search_products again with the same or similar query.
     Tell the user the item is not currently available and offer alternatives.
   - If you already have search results in the Observation, go directly to Final Answer.

4. PURCHASE FLOW:
   STEP 1: User mentions product - use search_products
   STEP 2: Show results clearly - ask which one they want
   STEP 3: User confirms - use place_order
   Do NOT call place_order without confirmed product.

5. LOCATION FLOW:
   User mentions city/governorate WITH product - use find_nearby_stores
   Format: 'product | location'  example: 'phone | cairo'

6. PRICE COMPARISON:
   If user asks for cheaper or comparison - search_products then show sorted by price.

7. ORDER HISTORY:
   If user asks about their orders - use get_order_history.

8. Multi-product: comma-separated - 'laptop, phone'
9. Greeting - greet back warmly.

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
    """Direct reply for greetings and general conversation."""
    return x


async def _place_order_stub(q: str) -> str:
    """Stub for order placement."""
    return "User confirmed purchase. Ask for name and phone if not already provided."


class TextAssistant:
    """Main text-based shopping assistant using LangChain agents."""

    def __init__(self):
        self._store   = ProductService()
        self._backend = BackendService()
        self._llm     = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            google_api_key=settings.GEMINI_API_KEY,
        )

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
        """
        Process user message and return assistant response with products/orders.
        """
        try:
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
            logger.error(f"Error processing message: {message}", exc_info=True)
            language = _detect_language(message)
            error_msg = "Sorry, I encountered an error processing your request. Please try again." if language == "English" else "عذراً، حدث خطأ في معالجة طلبك. حاول مرة أخرى."
            return {
                "response":           error_msg,
                "state":              "error",
                "products":           None,
                "order_confirmation": None,
                "nearby_stores":      None,
            }

    # ─── History Management ───────────────────────────────────────────────────

    async def _get_history(self, session_id: str) -> str:
        """Retrieve conversation history from database."""
        if not session_id:
            return "No previous conversation."
        try:
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
        except Exception as e:
            logger.error(f"Error retrieving history for session: {session_id}", exc_info=True)
            return "No previous conversation."

    async def _save_to_history(self, session_id: str, user_msg: str, assistant_msg: str):
        """Save conversation messages to database."""
        if not session_id:
            return
        try:
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
        except Exception as e:
            logger.error(f"Error saving history for session: {session_id}", exc_info=True)

    # ─── Search Logging ───────────────────────────────────────────────────────

    async def _log_search(self, query: str, count: int, customer_phone: str = None, gov: str = None):
        """Log search queries for analytics."""
        try:
            async with AsyncSessionFactory() as db:
                db.add(SearchLogModel(
                    query=query,
                    governorate=gov,
                    results_count=count,
                    customer_phone=customer_phone,
                ))
                await db.commit()
        except Exception as e:
            logger.warning(f"Failed to log search query: {query}", exc_info=True)

    # ─── Purchase Handling ────────────────────────────────────────────────────

    async def _handle_purchase(self, customer_name, customer_phone, selected_product) -> dict:
        """Handle purchase flow and order placement."""
        try:
            if not customer_name or not customer_phone:
                return {
                    "response": (
                        "Great! To complete the order, I need:\n"
                        "- Your full name\n"
                        "- Your phone number\n\n"
                        "Send them and I will contact the vendor immediately."
                    ),
                    "state": "awaiting_confirm",
                    "products": None, "order_confirmation": None, "nearby_stores": None,
                }

            product_name  = selected_product.get("title",    "")
            product_price = selected_product.get("price",    0)
            vendor_phone  = selected_product.get("shop_phone")
            shop_id       = selected_product.get("shop_id")
            shop_name     = selected_product.get("shop_name", "")

            # Fallback: look up vendor/store if not provided
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
                logger.info(f"Order placed successfully: {selected_product.get('id')} for {customer_phone}")
                return {
                    "response": (
                        f"Order submitted successfully!\n\n"
                        f"Product: {product_name}\n"
                        f"Price: {product_price} EGP\n"
                        f"Store: {shop_name}\n\n"
                        f"The vendor will contact you on {customer_phone} shortly."
                    ),
                    "state": "order_sent",
                    "products": None,
                    "order_confirmation": result.get("data"),
                    "nearby_stores": None,
                }
            else:
                logger.error(f"Failed to place order: {result}")
                return {
                    "response": "Failed to submit order. Please try again.",
                    "state": "product_found",
                    "products": None, "order_confirmation": None, "nearby_stores": None,
                }
        except Exception as e:
            logger.error(f"Error handling purchase", exc_info=True)
            return {
                "response": "An error occurred while processing your order. Please try again.",
                "state": "error",
                "products": None, "order_confirmation": None, "nearby_stores": None,
            }

    # ─── Agent Building ───────────────────────────────────────────────────────

    def _build_executor(
        self,
        request_products: list,
        user_lat:         float = None,
        user_lon:         float = None,
        language:         str   = "English",
        customer_phone:   str   = None,
    ) -> AgentExecutor:
        """Build LangChain agent executor with search and retrieval tools."""

        async def search_and_summarize(query: str) -> str:
            """Search for products and format results."""
            try:
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
                    if isinstance(products, Exception):
                        logger.error(f"Search error for: {sub_q}", exc_info=products)
                        all_lines.append(f"No products available for '{sub_q}'.")
                        continue

                    if not products:
                        logger.warning(f"No products found for: {sub_q}")
                        all_lines.append(
                            f"FINAL RESULT: No products found for '{sub_q}'. "
                            "Do NOT search again. Tell the user this item is not available."
                        )
                        continue

                    products = products[:5]
                    all_lines.append(f"Search results for '{sub_q}' ({len(products)} products):\n")

                    for i, p in enumerate(products, 1):
                        stores   = await self._backend.get_stores_for_product(p)
                        enriched = dict(p)

                        if stores:
                            enriched.update({
                                "shop_id":          stores[0]["id"],
                                "shop_name":        stores[0]["name"],
                                "shop_governorate": stores[0].get("governorate", ""),
                                "shop_phone":       stores[0].get("phone", ""),
                                "all_stores":       stores,
                            })

                        request_products.append(enriched)

                        stores_summary = " | ".join(
                            f"Store: {s['name']} ({s['governorate']})"
                            for s in stores[:3]
                        ) if stores else "Available"

                        all_lines.append(
                            f"  {i}. {p['title']}\n"
                            f"     Price: {p['price']} EGP | Category: {p['category']}\n"
                            f"     {stores_summary}\n"
                        )

                    asyncio.create_task(
                        self._log_search(sub_q, len(products), customer_phone)
                    )

                # NOTE: No instruction strings here — the prompt handles presentation logic.
                return "\n".join(all_lines)

            except Exception as e:
                logger.error(f"Error in search_and_summarize: {query}", exc_info=True)
                return "Unable to search for products. Please try again."

        async def find_nearby_stores(query: str) -> str:
            """Find stores near user location with specified product."""
            try:
                parts   = query.split("|")
                product = parts[0].strip()
                loc     = parts[1].strip() if len(parts) > 1 else ""

                lat, lon = user_lat, user_lon
                if not lat and loc:
                    coords = resolve_location(loc)
                    if coords:
                        lat, lon = coords

                if not lat:
                    return "Unable to determine your location. Please provide a city or governorate name."

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
                        return f"No products or stores available for '{product}'."
                    lines = [f"Product '{product}' not in catalog, but here are nearby stores:\n"]
                    for i, s in enumerate(sorted_stores[:5], 1):
                        lines.append(
                            f"  {i}. Store: {s['name']} - {s['governorate']}\n"
                            f"     Distance: {s.get('distance_km', '?')} km | Phone: {s.get('phone', '')}"
                        )
                    # NOTE: No instruction strings here — the prompt handles presentation logic.
                    return "\n".join(lines)

                lines = [f"Search results for '{product}' sorted by distance from {loc}:\n"]
                for i, p in enumerate(products, 1):
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
                        f"Store: {enriched.get('shop_name', '?')} - "
                        f"{enriched.get('shop_governorate', '?')} "
                        f"({enriched.get('shop_distance', '?')} km) | "
                        f"Phone: {enriched.get('shop_phone', '')}"
                        if p_sorted else "Available"
                    )
                    lines.append(
                        f"  {i}. {p['title']}\n"
                        f"     Price: {p['price']} EGP\n"
                        f"     {store_info}\n"
                    )

                # NOTE: No instruction strings here — the prompt handles presentation logic.
                return "\n".join(lines)

            except Exception as e:
                logger.error(f"Error in find_nearby_stores: {query}", exc_info=True)
                return "Unable to find nearby stores. Please try again."

        async def get_order_history(phone: str) -> str:
            """Get order history for a customer phone number."""
            try:
                from config.database import OrderModel
                clean = phone.strip().replace(" ", "")
                async with AsyncSessionFactory() as db:
                    stmt   = select(OrderModel).where(
                        OrderModel.customer_phone.like(f"%{clean[-8:]}%")
                    ).order_by(OrderModel.created_at.desc()).limit(5)
                    result = await db.execute(stmt)
                    rows   = result.scalars().all()

                if not rows:
                    return "No previous orders found for this phone number."

                lines = ["Order History:\n"]
                for r in rows:
                    lines.append(
                        f"- Order #{r.id} - {r.product_name} - {r.product_price} EGP\n"
                        f"  Status: {r.status} | Date: {str(r.created_at)[:10]}"
                    )
                return "\n".join(lines)

            except Exception as e:
                logger.error(f"Error retrieving order history: {phone}", exc_info=True)
                return "Unable to retrieve order history. Please try again."

        async def browse_category(category: str) -> str:
            """Browse products in a specific category."""
            try:
                products = (await self._store.by_category(category))[:5]
                if not products:
                    return f"No products found in category: {category}"
                lines = [f"Products in {category}:\n"]
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
                    lines.append(f"{i}. {p['title']} | {p['price']} EGP | ID: {p['id']}")
                # NOTE: No instruction strings here — the prompt handles presentation logic.
                return "\n".join(lines)

            except Exception as e:
                logger.error(f"Error browsing category: {category}", exc_info=True)
                return "Unable to browse category. Please try again."

        # ─── Tools Configuration ──────────────────────────────────────────────

        tools = [
            Tool.from_function(
                name="direct_reply",
                func=lambda x: x, coroutine=_direct_reply,
                description="Use for greetings, farewells, and general conversation.",
            ),
            Tool.from_function(
                name="search_products",
                func=lambda q: q, coroutine=search_and_summarize,
                description="Search for products in English or Arabic. Multiple items: 'laptop, phone'. Use when no city mentioned.",
            ),
            Tool.from_function(
                name="get_by_category",
                func=lambda c: c, coroutine=browse_category,
                description="Get products by category: electronics, jewelery, mens clothing, womens clothing, beauty, fragrances, furniture, groceries.",
            ),
            Tool.from_function(
                name="find_nearby_stores",
                func=lambda q: q, coroutine=find_nearby_stores,
                description="Search for products near a location. Format: 'product | location' example: 'phone | cairo'.",
            ),
            Tool.from_function(
                name="get_order_history",
                func=lambda p: p, coroutine=get_order_history,
                description="Get order history for a customer. Input: phone number.",
            ),
            Tool.from_function(
                name="place_order",
                func=lambda q: "Ask for customer details.",
                coroutine=_place_order_stub,
                description="Use only when customer confirms specific product: 'I want it', 'the first one'.",
            ),
        ]

        agent = create_react_agent(
            llm=self._llm,
            tools=tools,
            prompt=PromptTemplate.from_template(_PROMPT),
        )

        return AgentExecutor(
            callbacks=[],
            agent=agent,
            tools=tools,
            verbose=settings.AGENT_VERBOSE,
            handle_parsing_errors=True,
            max_iterations=settings.AGENT_MAX_ITERATIONS,
            early_stopping_method="force",
            return_intermediate_steps=False,
        )