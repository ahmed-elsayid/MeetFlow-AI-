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


def _serialize(items: list) -> str:
    """Serialize a list of Pydantic models or plain strings for prompt injection."""
    parts: list[str] = []
    for item in items:
        if hasattr(item, "model_dump"):
            parts.append(json.dumps(item.model_dump(), default=str))
        else:
            parts.append(str(item))
    return "\n".join(parts) if parts else "(none)"


async def _draft_email(
    llm,
    prompt_template: str,
    fmt_kwargs: dict,
    variant: str,
    recipients: list[str],
    fallback_subject: str,
) -> EmailDraft:
    """Call the LLM to draft one email variant. Returns a fallback draft on any error."""
    try:
        prompt = prompt_template.format(**fmt_kwargs)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        raw = (
            response.content.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(
                "Email drafter (%s): LLM output not valid JSON — wrapping as HTML. "
                "First 300 chars: %s",
                variant, raw[:300],
            )
            data = {
                "subject": fallback_subject,
                "body_html": f"<html><body><pre>{raw}</pre></body></html>",
            }

        return EmailDraft(
            variant=variant,
            subject=data.get("subject", fallback_subject),
            body_html=data.get("body_html", ""),
            recipients=recipients,
        )

    except Exception as exc:
        logger.exception(
            "Email drafter (%s): LLM call failed — %s: %s",
            variant, type(exc).__name__, exc,
        )
        return EmailDraft(
            variant=variant,
            subject=fallback_subject,
            body_html=(
                "<html><body>"
                "<p><strong>Email generation failed.</strong></p>"
                f"<p>Error: {type(exc).__name__}: {exc}</p>"
                "</body></html>"
            ),
            recipients=recipients,
        )


async def email_drafter_node(state: MeetingState) -> dict:
    """Post-meeting node: drafts participant and stakeholder recap emails."""
    meeting_id = state.get("meeting_id", "unknown")
    notes = state.get("notes", [])
    decisions = state.get("decisions", [])
    tasks = state.get("tasks", [])
    research = state.get("research", [])
    recipient_emails: list[str] = state.get("recipient_emails", [])
    stakeholder_emails: list[str] = state.get("stakeholder_emails", []) or recipient_emails

    # Build LLM lazily inside the node so import-time failures don't block startup
    llm = build_llm(max_tokens=4096, temperature=0)

    logger.info(
        "Email drafter: meeting=%s notes=%d decisions=%d tasks=%d recipients=%d",
        meeting_id, len(notes), len(decisions), len(tasks), len(recipient_emails),
    )

    participant_draft = await _draft_email(
        llm=llm,
        prompt_template=PARTICIPANT_PROMPT,
        fmt_kwargs={
            "meeting_id": meeting_id,
            "notes": _serialize(notes),
            "decisions": _serialize(decisions),
            "tasks": _serialize(tasks),
            "research": _serialize(research),
        },
        variant="participant",
        recipients=recipient_emails,
        fallback_subject=f"Meeting Recap: {meeting_id}",
    )

    stakeholder_draft = await _draft_email(
        llm=llm,
        prompt_template=STAKEHOLDER_PROMPT,
        fmt_kwargs={
            "meeting_id": meeting_id,
            "notes": _serialize(notes),
            "decisions": _serialize(decisions),
        },
        variant="stakeholder",
        recipients=stakeholder_emails,
        fallback_subject=f"Meeting Brief: {meeting_id}",
    )

    return {"email_drafts": [participant_draft, stakeholder_draft]}
