from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from app.config import settings
from app.models.enums import ChunkClassification
from app.models.schemas import ClassifiedChunk, TranscriptChunk

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (Path(__file__).resolve().parent.parent.parent / "prompts" / "classifier.txt").read_text()

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=settings.anthropic_api_key,
    max_tokens=256,
    temperature=0,
)


async def classify_chunk(
    chunk: TranscriptChunk,
    recent_chunks: list[TranscriptChunk] | None = None,
) -> ClassifiedChunk:
    context = ""
    if recent_chunks:
        context = "\n".join(
            f"[{c.speaker}]: {c.text}" for c in recent_chunks[-5:]
        )

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


def route_by_classification(state: dict) -> list[str]:
    """Return the next node(s) based on the latest classification."""
    classified = state.get("classified", [])
    if not classified:
        return ["discard"]

    latest = classified[-1]
    label = latest.classification

    routing = {
        ChunkClassification.DECISION.value: ["notetaker"],
        ChunkClassification.DISCUSSION.value: ["notetaker"],
        ChunkClassification.TASK_COMMITMENT.value: ["task_extractor"],
        ChunkClassification.RESEARCH_TRIGGER.value: ["researcher"],
        ChunkClassification.OFF_TOPIC.value: ["discard"],
    }
    return routing.get(label, ["discard"])
