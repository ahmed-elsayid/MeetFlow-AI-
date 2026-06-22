from __future__ import annotations

from app.models.schemas import EmailDraft, ExtractedTask


def email_approval_card(draft: EmailDraft, request_id: str = "") -> dict:
    """Build a Teams Adaptive Card for email approval.

    Shows the email subject and a preview of the body, with
    Approve / Edit / Reject action buttons.
    """
    body_preview = draft.body_html[:500]
    if len(draft.body_html) > 500:
        body_preview += "..."

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Email Approval Required",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": f"**Variant:** {draft.variant}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": f"**Subject:** {draft.subject}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": "**Body preview:**",
                "spacing": "Medium",
            },
            {
                "type": "TextBlock",
                "text": body_preview,
                "wrap": True,
                "maxLines": 10,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Approve",
                "style": "positive",
                "data": {
                    "request_id": request_id,
                    "action": "approve",
                },
            },
            {
                "type": "Action.Submit",
                "title": "Edit",
                "data": {
                    "request_id": request_id,
                    "action": "edit",
                },
            },
            {
                "type": "Action.Submit",
                "title": "Reject",
                "style": "destructive",
                "data": {
                    "request_id": request_id,
                    "action": "reject",
                },
            },
        ],
    }


def task_approval_card(task: ExtractedTask, request_id: str = "") -> dict:
    """Build a Teams Adaptive Card for task approval.

    Shows task details (description, assignee, deadline, priority)
    with Approve / Reject action buttons.
    """
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": "Task Approval Required",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "FactSet",
                "facts": [
                    {"title": "Description", "value": task.task_description},
                    {"title": "Assignee", "value": task.assignee},
                    {"title": "Deadline", "value": task.deadline or "Not set"},
                    {"title": "Priority", "value": task.priority},
                ],
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Approve",
                "style": "positive",
                "data": {
                    "request_id": request_id,
                    "action": "approve",
                },
            },
            {
                "type": "Action.Submit",
                "title": "Reject",
                "style": "destructive",
                "data": {
                    "request_id": request_id,
                    "action": "reject",
                },
            },
        ],
    }
