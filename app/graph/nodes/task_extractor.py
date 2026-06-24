"""Task extractor agent node — pulls action items from classified transcript chunks."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.config import settings
from app.graph.nodes._llm import build_llm
from app.graph.state import MeetingState
from app.models.enums import ChunkClassification
from app.models.schemas import ExtractedTask
from app.services.jira_client import JiraClient

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / "task_extractor.txt"


async def task_extractor_node(state: MeetingState) -> dict:
    """LangGraph node: extract tasks from task-commitment chunks."""

    # ------------------------------------------------------------------ #
    #  1. Filter task-commitment chunks
    # ------------------------------------------------------------------ #
    task_chunks = [
        c for c in state["classified"]
        if c.classification == ChunkClassification.TASK_COMMITMENT.value
    ]

    if not task_chunks:
        logger.info("Task extractor: no task-commitment chunks to process.")
        return {"tasks": []}

    # ------------------------------------------------------------------ #
    #  2. Build prompt
    # ------------------------------------------------------------------ #
    try:
        prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"Prompt file not found: {PROMPT_PATH}"
        logger.error(msg)
        return {"error_log": [msg]}

    chunks_text = "\n".join(
        f"[{c.chunk.timestamp_start}] {c.chunk.speaker}: {c.chunk.text}"
        for c in task_chunks
    )

    prompt = prompt_template.format(
        chunks=chunks_text,
        today=date.today().isoformat(),
    )

    # ------------------------------------------------------------------ #
    #  3. Call Claude
    # ------------------------------------------------------------------ #
    try:
        llm = build_llm(max_tokens=2048)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = response.content
    except Exception as exc:
        msg = f"Task extractor LLM call failed: {exc}"
        logger.exception(msg)
        return {"error_log": [msg]}

    # ------------------------------------------------------------------ #
    #  4. Parse response
    # ------------------------------------------------------------------ #
    try:
        data = json.loads(raw)
        tasks = [ExtractedTask(**t) for t in data.get("tasks", [])]
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        msg = f"Task extractor failed to parse LLM response: {exc}"
        logger.error(msg)
        return {"error_log": [msg]}

    # ------------------------------------------------------------------ #
    #  5. Create Jira tickets for non-ambiguous tasks (best-effort)
    # ------------------------------------------------------------------ #
    if settings.jira_base_url and settings.jira_api_token:
        jira = JiraClient()
        for task in tasks:
            if task.is_ambiguous:
                logger.info(
                    "Task is ambiguous, skipping Jira (needs human review): %s",
                    task.task_description,
                )
                continue

            try:
                browse_url = await jira.create_issue(task)
                task.jira_ticket_url = browse_url
                logger.info("Created Jira ticket: %s", browse_url)
            except Exception as exc:
                logger.warning(
                    "Jira ticket creation failed for '%s': %s",
                    task.task_description,
                    exc,
                )

    return {"tasks": tasks}
