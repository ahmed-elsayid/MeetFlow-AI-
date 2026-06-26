from __future__ import annotations

import logging

from app.config import settings
from app.graph.state import MeetingState
from app.hitl.adaptive_cards import email_approval_card
from app.hitl.gate import hitl_gate, wait_for_approval
from app.models.enums import ApprovalStatus
from app.services.email_client import email_client

logger = logging.getLogger(__name__)


async def email_sender_node(state: MeetingState) -> dict:
    """Post-meeting node: send drafted emails, gated by HITL approval when configured."""
    drafts = state.get("email_drafts", [])

    if not drafts:
        logger.info("Email sender: no drafts to send.")
        return {}

    error_log: list[str] = []

    for draft in drafts:
        if not draft.recipients:
            logger.warning("Skipping '%s' — no recipients.", draft.subject)
            error_log.append(f"skipped (no recipients): {draft.subject}")
            continue

        # Human-in-the-loop gate: require approval before sending
        if settings.hitl_timeout_seconds > 0:
            card = email_approval_card(draft)
            approval = await hitl_gate(
                action_type="email_send",
                payload={"adaptive_card": card, "draft": draft.model_dump()},
            )
            status, edited_payload = await wait_for_approval(
                request_id=approval.request_id,
                timeout=settings.hitl_timeout_seconds,
            )

            if status == ApprovalStatus.REJECTED:
                logger.info("Email rejected by reviewer: %s", draft.subject)
                error_log.append(f"rejected: {draft.subject}")
                continue

            if status == ApprovalStatus.TIMED_OUT:
                logger.warning(
                    "HITL timed out for '%s' — auto-approving", draft.subject
                )

            # If the reviewer edited the draft, use their version instead
            if status == ApprovalStatus.EDITED and edited_payload:
                edited_draft_data = edited_payload.get("draft", {})
                if edited_draft_data:
                    from app.models.schemas import EmailDraft as _EmailDraft
                    try:
                        draft = _EmailDraft(
                            variant=edited_draft_data.get("variant", draft.variant),
                            subject=edited_draft_data.get("subject", draft.subject),
                            body_html=edited_draft_data.get("body_html", draft.body_html),
                            recipients=edited_draft_data.get("recipients", draft.recipients),
                        )
                        logger.info("Using reviewer-edited draft for: %s", draft.subject)
                    except Exception as exc:
                        logger.warning("Could not apply edited draft — sending original: %s", exc)

        success = await email_client.send(draft)
        if success:
            logger.info("Email sent: %s", draft.subject)
        else:
            logger.warning("Email send failed: %s", draft.subject)
            error_log.append(f"send failed: {draft.subject}")

    return {"error_log": error_log} if error_log else {}
