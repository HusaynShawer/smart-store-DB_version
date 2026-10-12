# app/agents/graph.py
"""
LangGraph assembly — a deterministic state-machine agent.

Flow:
  START → load_context → route_intent ──(conditional)──► search / category / nearby
                                                        └──► purchase ▶ respond ◄──┘
                                                            greet / chat    └► END
Nodes run inside `AgentNodes`, bound to the request's DB session (dependency
injection); the compiled graph is cheap to re-create per conversation turn.
"""
from collections.abc import Mapping

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import AgentNodes
from app.agents.state import AgentState
from app.core.llm import ChatLLM

INTENT_TO_NODE: Mapping[str, str] = {
    "greet": "respond",
    "chat": "respond",
    "search": "search",
    "category": "category",
    "nearby": "nearby",
    "purchase": "purchase",
}


def _route_after_intent(state: AgentState) -> str:
    return INTENT_TO_NODE.get(state.get("intent", ""), "respond")


def build_graph(session, llm: ChatLLM | None = None):
    """Compile the agent graph for one request (session-scoped services)."""
    nodes = AgentNodes(session, llm or ChatLLM())

    g = StateGraph(AgentState)
    g.add_node("load_context", nodes.load_context)
    g.add_node("route_intent", nodes.route_intent)
    g.add_node("search", nodes.search_products)
    g.add_node("category", nodes.category_products)
    g.add_node("nearby", nodes.nearby_stores)
    g.add_node("purchase", nodes.place_order)
    g.add_node("respond", nodes.respond)

    g.add_edge(START, "load_context")
    g.add_edge("load_context", "route_intent")
    g.add_conditional_edges("route_intent", _route_after_intent, list(INTENT_TO_NODE.values()))

    for node in ("search", "category", "nearby", "purchase"):
        g.add_edge(node, "respond")
    g.add_edge("respond", END)

    return g.compile()