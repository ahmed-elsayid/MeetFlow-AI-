from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from app.graph.nodes.email_drafter import email_drafter_node
from app.graph.nodes.email_sender import email_sender_node
from app.graph.nodes.notetaker import notetaker_node
from app.graph.nodes.researcher import researcher_node
from app.graph.nodes.task_extractor import task_extractor_node
from app.graph.orchestrator import classify_chunk, route_by_classification
from app.graph.state import MeetingState
from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)


async def classify_node(state: MeetingState) -> dict:
    """Classify the latest transcript chunk."""
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


async def compile_summary_node(state: MeetingState) -> dict:
    """Collect all agent outputs into the final state — no transformation needed,
    LangGraph's accumulation already has everything."""
    return {}


def build_live_graph() -> StateGraph:
    """Build the graph used during a live meeting to process individual chunks."""
    graph = StateGraph(MeetingState)

    graph.add_node("classify", classify_node)
    graph.add_node("notetaker", notetaker_node)
    graph.add_node("task_extractor", task_extractor_node)
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
    """Build the graph used after a meeting ends to generate and send emails."""
    graph = StateGraph(MeetingState)

    graph.add_node("email_drafter", email_drafter_node)
    graph.add_node("email_sender", email_sender_node)

    graph.set_entry_point("email_drafter")
    graph.add_edge("email_drafter", "email_sender")
    graph.add_edge("email_sender", END)

    return graph.compile()
