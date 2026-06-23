"""Notetaker agent node — structures classified transcript chunks into meeting notes."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.config import settings
from app.graph.nodes._llm import build_llm
from app.graph.state import MeetingState
from app.models.enums import ChunkClassification
from app.models.schemas import NoteSection
from app.services.notion_client import NotionClient

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "notetaker.txt"


async def notetaker_node(state: MeetingState) -> dict:
    """LangGraph node: convert discussion/decision chunks into structured notes."""

    # ------------------------------------------------------------------ #
    #  1. Filter relevant chunks
    # ------------------------------------------------------------------ #
    relevant_types = {ChunkClassification.DISCUSSION, ChunkClassification.DECISION}
    classified = [
        c for c in state["classified"]
        if c.classification in {t.value for t in relevant_types}
    ]

    if not classified:
        logger.info("Notetaker: no discussion/decision chunks to process.")
        return {"notes": [], "decisions": []}

    # ------------------------------------------------------------------ #
    #  2. Build prompt
    # ------------------------------------------------------------------ #
    try:
        prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"Prompt file not found: {PROMPT_PATH}"
        logger.error(msg)
        return {"error_log": [msg]}

    existing_notes = "\n".join(
        f"- {section.topic}: {'; '.join(section.points)}"
        for section in state.get("notes", [])
    ) or "(none)"

    chunks_text = "\n".join(
        f"[{c.chunk.timestamp_start}] {c.chunk.speaker}: {c.chunk.text}"
        for c in classified
    )

    prompt = prompt_template.format(
        existing_notes=existing_notes,
        chunks=chunks_text,
    )

    # ------------------------------------------------------------------ #
    #  3. Call Claude
    # ------------------------------------------------------------------ #
    try:
        llm = build_llm(max_tokens=2048)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content
    except Exception as exc:
        msg = f"Notetaker LLM call failed: {exc}"
        logger.exception(msg)
        return {"error_log": [msg]}

    # ------------------------------------------------------------------ #
    #  4. Parse response
    # ------------------------------------------------------------------ #
    try:
        data = json.loads(raw)
        sections = [NoteSection(**s) for s in data.get("sections", [])]
        decisions: list[str] = data.get("decisions", [])
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        msg = f"Notetaker failed to parse LLM response: {exc}"
        logger.error(msg)
        return {"error_log": [msg]}

    # ------------------------------------------------------------------ #
    #  5. Push to Notion (best-effort)
    # ------------------------------------------------------------------ #
    try:
        if settings.notion_api_key and settings.notion_database_id:
            notion = NotionClient()
            meeting_id = state["meeting_id"]
            page_id = await notion.create_meeting_page(meeting_id, title=meeting_id)
            await notion.append_notes(page_id, sections)
            await notion.append_decisions(page_id, decisions)
            logger.info("Notes pushed to Notion for meeting %s", meeting_id)
    except Exception as exc:
        logger.warning("Notion push failed (non-fatal): %s", exc)

    return {"notes": sections, "decisions": decisions}
