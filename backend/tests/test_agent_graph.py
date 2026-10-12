# tests/test_agent_graph.py
"""LangGraph agent tests with a stubbed LLM (no network / no DB needed)."""
import pytest

from app.agents.graph import build_graph

# Search/nearby/purchase nodes touch the DB; only chat/greet paths run off-DB.


class StubChatLLM:
    """Scripted fake chat model for deterministic tests."""

    def __init__(self, intent, reply):
        self._intent = intent
        self._reply = reply

    async def acomplete_json(self, system, user):
        return {"intent": self._intent}

    async def acomplete(self, system, user):
        return self._reply


async def test_greeting_flow_returns_llm_reply():
    graph = build_graph(session=None, llm=StubChatLLM(intent="greet", reply="أهلاً وسهلاً 👋"))
    state = await graph.ainvoke({"input": "السلام عليكم", "answer_state": "conversation"})
    assert state["intent"] == "greet"
    assert state["language"] == "Arabic"
    assert state["response"] == "أهلاً وسهلاً 👋"


async def test_chat_flow_no_products():
    graph = build_graph(session=None, llm=StubChatLLM(intent="chat", reply="إيه اللي تحب تسأل عنه؟"))
    state = await graph.ainvoke({"input": "شكرا", "answer_state": "conversation"})
    assert state["intent"] == "chat"
    assert state.get("products") is None


async def test_llm_router_fallback_still_runs():
    # Router returns garbage → keyword fallback → "greet"
    graph = build_graph(session=None, llm=StubChatLLM(intent="gibberish", reply="هاي 👋"))
    state = await graph.ainvoke({"input": "مرحبا", "answer_state": "conversation"})
    assert state["intent"] == "greet"
    assert state["response"] == "هاي 👋"