from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.graph.nodes.email_drafter import email_drafter_node
from app.graph.nodes.email_sender import email_sender_node
from app.graph.nodes.notetaker import notetaker_node
from app.graph.nodes.researcher import researcher_node
from app.graph.nodes.task_extractor import action_tasks_node
from app.graph.orchestrator import classify_chunk, route_by_classification
from app.graph.state import MeetingState

logger = logging.getLogger(__name__)


async def classify_node(state: MeetingState) -> dict:
    """Classify the latest transcript chunk and append to state.classified."""
    chunks = state.get("chunks", [])
    if not chunks:
        return {"error_log": ["classify_node: no chunks to classify"]}

    latest = chunks[-1]
    recent = chunks[-6:-1] if len(chunks) > 1 else []

    try:
        classified = await classify_chunk(latest, recent)
        return {"classified": [classified]}
    except Exception as e:
        logger.exception("Classification failed")
        return {"error_log": [f"classify_node error: {e}"]}


async def discard_node(state: MeetingState) -> dict:
    """No-op for off-topic chunks."""
    return {}


def build_live_graph() -> StateGraph:
    """Build the graph that processes live transcript chunks one at a time.

    Flow: classify → conditional route → {notetaker | task_extractor | researcher | discard}
    Each branch writes back into the accumulated state (add reducer).
    """
    graph = StateGraph(MeetingState)

    graph.add_node("classify", classify_node)
    graph.add_node("notetaker", notetaker_node)
    graph.add_node("task_extractor", action_tasks_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("discard", discard_node)

    graph.set_entry_point("classify")

    graph.add_conditional_edges(
        "classify",
        route_by_classification,
        {
            "notetaker": "notetaker",
            "task_extractor": "task_extractor",
            "researcher": "researcher",
            "discard": "discard",
        },
    )

    graph.add_edge("notetaker", END)
    graph.add_edge("task_extractor", END)
    graph.add_edge("researcher", END)
    graph.add_edge("discard", END)

    return graph.compile()


def build_post_meeting_graph() -> StateGraph:
    """Build the graph used after a meeting ends.

    Flow:
      notetaker       — full transcript pass, writes to Notion
        → task_extractor — creates Jira tickets from action items
          → email_drafter  — composes participant + stakeholder recap emails
            → email_sender — HITL gate → send via SMTP
    """
    graph = StateGraph(MeetingState)

    graph.add_node("notetaker", notetaker_node)
    graph.add_node("task_extractor", action_tasks_node)
    graph.add_node("email_drafter", email_drafter_node)
    graph.add_node("email_sender", email_sender_node)

    graph.set_entry_point("notetaker")
    graph.add_edge("notetaker", "task_extractor")
    graph.add_edge("task_extractor", "email_drafter")
    graph.add_edge("email_drafter", "email_sender")
    graph.add_edge("email_sender", END)

    return graph.compile()
