from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.graph.nodes._llm import build_llm
from app.models.enums import ChunkClassification
from app.models.schemas import ClassifiedChunk, TranscriptChunk

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent / "prompts" / "classifier.txt"
).read_text()

# Module-level LLM — cheap to instantiate, safe to share across requests
llm = build_llm(max_tokens=256, temperature=0)


async def classify_chunk(
    chunk: TranscriptChunk,
    recent_chunks: list[TranscriptChunk] | None = None,
) -> ClassifiedChunk:
    context = ""
    if recent_chunks:
        context = "\n".join(f"[{c.speaker}]: {c.text}" for c in recent_chunks[-5:])

    prompt = PROMPT_TEMPLATE.format(
        context=context or "(no prior context)",
        speaker=chunk.speaker,
        text=chunk.text,
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Failed to parse classifier output: %s", raw)
        data = {"classification": "discussion", "confidence": 0.5}

    classification = data.get("classification", "discussion")
    if classification not in {e.value for e in ChunkClassification}:
        classification = "discussion"

    return ClassifiedChunk(
        chunk=chunk,
        classification=classification,
        confidence=float(data.get("confidence", 0.5)),
    )


def route_by_classification(state: dict) -> str:
    """Return the name of the next live-graph node based on the latest classification.

    Notes (decision / discussion) are captured in the live graph via a lightweight
    notetaker call.  Full summarisation + Notion write happens in the post-meeting
    graph, so the live routing still dispatches to ``notetaker`` for those labels.
    """
    classified = state.get("classified", [])
    if not classified:
        return "discard"

    latest = classified[-1]
    label = latest.classification

    routing = {
        ChunkClassification.DECISION.value: "notetaker",
        ChunkClassification.DISCUSSION.value: "notetaker",
        ChunkClassification.TASK_COMMITMENT.value: "task_extractor",
        ChunkClassification.RESEARCH_TRIGGER.value: "researcher",
        ChunkClassification.OFF_TOPIC.value: "discard",
    }
    return routing.get(label, "discard")
