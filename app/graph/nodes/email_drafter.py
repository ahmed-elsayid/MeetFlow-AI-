from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.graph.nodes._llm import build_llm
from app.graph.state import MeetingState
from app.models.schemas import EmailDraft

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "prompts"
PARTICIPANT_PROMPT = (PROMPTS_DIR / "email_participant.txt").read_text()
STAKEHOLDER_PROMPT = (PROMPTS_DIR / "email_stakeholder.txt").read_text()

llm = build_llm(max_tokens=4096, temperature=0)


def _serialize(items: list) -> str:
    """Serialize a list of Pydantic models or plain strings for prompt injection."""
    parts: list[str] = []
    for item in items:
        if hasattr(item, "model_dump"):
            parts.append(json.dumps(item.model_dump(), default=str))
        else:
            parts.append(str(item))
    return "\n".join(parts) if parts else "(none)"


async def email_drafter_node(state: MeetingState) -> dict:
    """Post-meeting node: drafts participant and stakeholder recap emails."""
    meeting_id = state.get("meeting_id", "unknown")
    notes = state.get("notes", [])
    decisions = state.get("decisions", [])
    tasks = state.get("tasks", [])
    research = state.get("research", [])
    recipient_emails: list[str] = state.get("recipient_emails", [])
    stakeholder_emails: list[str] = state.get("stakeholder_emails", []) or recipient_emails

    drafts: list[EmailDraft] = []

    # --- Participant email ---
    try:
        participant_prompt = PARTICIPANT_PROMPT.format(
            meeting_id=meeting_id,
            notes=_serialize(notes),
            decisions=_serialize(decisions),
            tasks=_serialize(tasks),
            research=_serialize(research),
        )

        response = await llm.ainvoke([HumanMessage(content=participant_prompt)])
        raw = response.content.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse participant email output: %s", raw[:200])
            data = {
                "subject": f"Meeting Recap: {meeting_id}",
                "body_html": f"<html><body>{raw}</body></html>",
            }

        drafts.append(
            EmailDraft(
                variant="participant",
                subject=data.get("subject", f"Meeting Recap: {meeting_id}"),
                body_html=data.get("body_html", ""),
                recipients=recipient_emails,
            )
        )
    except Exception:
        logger.exception("Failed to draft participant email")
        drafts.append(
            EmailDraft(
                variant="participant",
                subject=f"Meeting Recap: {meeting_id}",
                body_html="<html><body><p>Email generation failed.</p></body></html>",
                recipients=recipient_emails,
            )
        )

    # --- Stakeholder email ---
    try:
        stakeholder_prompt = STAKEHOLDER_PROMPT.format(
            meeting_id=meeting_id,
            notes=_serialize(notes),
            decisions=_serialize(decisions),
        )

        response = await llm.ainvoke([HumanMessage(content=stakeholder_prompt)])
        raw = response.content.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Failed to parse stakeholder email output: %s", raw[:200])
            data = {
                "subject": f"Meeting Brief: {meeting_id}",
                "body_html": f"<html><body>{raw}</body></html>",
            }

        drafts.append(
            EmailDraft(
                variant="stakeholder",
                subject=data.get("subject", f"Meeting Brief: {meeting_id}"),
                body_html=data.get("body_html", ""),
                recipients=stakeholder_emails,
            )
        )
    except Exception:
        logger.exception("Failed to draft stakeholder email")
        drafts.append(
            EmailDraft(
                variant="stakeholder",
                subject=f"Meeting Brief: {meeting_id}",
                body_html="<html><body><p>Email generation failed.</p></body></html>",
                recipients=stakeholder_emails,
            )
        )

    return {"email_drafts": drafts}
