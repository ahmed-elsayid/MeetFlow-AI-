from __future__ import annotations

import logging

from app.graph.state import MeetingState
from app.services.email_client import email_client

logger = logging.getLogger(__name__)


async def email_sender_node(state: MeetingState) -> dict:
    """Post-meeting node: sends all drafted emails via Graph API or SMTP."""
    drafts = state.get("email_drafts", [])

    if not drafts:
        logger.info("Email sender: no drafts to send.")
        return {}

    results: list[str] = []
    for draft in drafts:
        if not draft.recipients:
            logger.warning("Skipping draft '%s' — no recipients set.", draft.subject)
            results.append(f"skipped (no recipients): {draft.subject}")
            continue

        success = await email_client.send(draft)
        status = "sent" if success else "failed"
        results.append(f"{status}: {draft.subject}")
        logger.info("Email %s — %s", status, draft.subject)

    return {"error_log": [r for r in results if r.startswith("failed")]}
