"""Task extractor — parses action items from meeting state, creates Jira tasks
via MCP stdio transport, and returns structured ExtractedTask records."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.graph.nodes._llm import build_llm
from app.models.schemas import ExtractedTask

logger = logging.getLogger(__name__)

# Path to the Jira MCP server script (lives in app/services/)
_JIRA_MCP_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "services" / "jira_client.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_email(name: str | None, recipient_emails: list[str]) -> str | None:
    """Match an assignee name to an email from the recipients list (fuzzy)."""
    if not name or name.lower() in ("unassigned", ""):
        return None

    name_lower = name.lower().strip()
    for email in recipient_emails:
        local = email.split("@")[0].lower()
        parts = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
        for part in name_lower.split():
            if part in parts or any(part in p for p in parts):
                return email
    return None


async def _parse_action_items(llm, action_items: list[str]) -> list[dict]:
    """Ask the LLM to extract structured task data from raw action item strings."""
    prompt = (
        "You are a project management assistant.\n"
        "For each action item below, extract:\n"
        '- "task": clean, concise task title\n'
        '- "assignee_name": full name of the responsible person, or "Unassigned"\n'
        '- "due_date": YYYY-MM-DD if mentioned, else null\n'
        '- "priority": "Highest"|"High"|"Medium"|"Low"|"Lowest" (default "Medium")\n'
        '- "notes": additional context, or null\n\n'
        "Return ONLY a valid JSON array, no markdown, no backticks.\n"
        "[\n"
        '  {"task": "...", "assignee_name": "...", "due_date": "...", "priority": "...", "notes": "..."}\n'
        "]\n\n"
        f"Action items:\n{json.dumps(action_items, indent=2)}"
    )

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = (
        response.content.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    parsed = json.loads(raw)
    logger.info("LLM parsed %d action items", len(parsed))
    return parsed


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

async def action_tasks_node(state: dict) -> dict:
    """LangGraph node: parse action items and create Jira tasks via MCP."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    action_items: list[str] = list(state.get("action_items", []))
    meeting_id: str = state.get("meeting_id", "unknown-meeting")
    recipient_emails: list[str] = state.get("recipient_emails", [])

    # Live-mode fallback: if no action_items from notetaker, extract directly
    # from the latest task_commitment classified chunk.
    if not action_items:
        classified = state.get("classified", [])
        for c in reversed(classified):
            label = c.classification if hasattr(c, "classification") else c.get("classification", "")
            if label == "task_commitment":
                text = c.chunk.text if hasattr(c, "chunk") else (c.get("chunk") or {}).get("text", "")
                if text:
                    action_items = [text]
                break

    # Post-meeting fallback: derive action items from the full transcript or notes
    # when there are no live-classified chunks (e.g. uploaded transcript flow).
    if not action_items:
        transcript = state.get("transcript", "")
        notes = state.get("notes", [])
        decisions = state.get("decisions", [])

        context_parts: list[str] = []
        if transcript:
            context_parts.append(f"TRANSCRIPT:\n{transcript[:4000]}")
        if decisions:
            context_parts.append("DECISIONS:\n" + "\n".join(f"- {d}" for d in decisions))
        for section in notes:
            if hasattr(section, "topic"):
                pts = "\n".join(f"  - {p}" for p in section.points)
                context_parts.append(f"{section.topic}:\n{pts}")
            elif isinstance(section, dict):
                pts = "\n".join(f"  - {p}" for p in section.get("points", []))
                context_parts.append(f"{section.get('topic', '')}:\n{pts}")

        if context_parts:
            extract_llm = build_llm(max_tokens=512, temperature=0)
            extract_prompt = (
                "Extract all action items, tasks, and follow-ups from this meeting content.\n"
                "Return ONLY a valid JSON array of strings, one per item. No markdown, no backticks.\n\n"
                + "\n\n".join(context_parts)
            )
            try:
                response = await extract_llm.ainvoke([HumanMessage(content=extract_prompt)])
                raw = (
                    response.content.strip()
                    .removeprefix("```json")
                    .removeprefix("```")
                    .removesuffix("```")
                    .strip()
                )
                action_items = json.loads(raw)
                logger.info("Post-meeting: extracted %d action items from transcript/notes", len(action_items))
            except Exception as exc:
                logger.warning("Post-meeting action item extraction failed: %s", exc)

    if not action_items:
        logger.info("No action items to process.")
        return {"tasks": []}

    logger.info(
        "Processing %d action item(s) for meeting %s", len(action_items), meeting_id
    )

    llm = build_llm(max_tokens=1024, temperature=0)

    try:
        parsed_tasks = await _parse_action_items(llm, action_items)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse action items: %s", exc)
        return {"tasks": [], "error_log": [f"task parse error: {exc}"]}
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return {"tasks": [], "error_log": [f"task LLM error: {exc}"]}

    bulk_tasks: list[dict] = []
    for task in parsed_tasks:
        assignee_name = task.get("assignee_name", "Unassigned")
        assignee_email = _resolve_email(assignee_name, recipient_emails)
        if assignee_email:
            logger.info("Resolved '%s' → %s", assignee_name, assignee_email)
        else:
            logger.warning("No email match for '%s' — task will be unassigned", assignee_name)

        notes_text = task.get("notes") or ""
        bulk_tasks.append({
            "summary": task.get("task", "Untitled Task"),
            "description": f"Meeting: {meeting_id}\nAssignee: {assignee_name}\n\n{notes_text}".strip(),
            "assignee_email": assignee_email,
            "due_date": task.get("due_date"),
            "priority": task.get("priority", "Medium"),
            "issue_type": "Task",
        })

    # Create Jira issues via MCP
    created_tasks: list[ExtractedTask] = []
    try:
        from app.config import settings

        jira_base_url = (os.environ.get("JIRA_BASE_URL") or settings.jira_base_url or "").strip()
        if not jira_base_url or "your-domain" in jira_base_url:
            logger.warning(
                "JIRA_BASE_URL is not configured (got %r) — skipping Jira ticket creation. "
                "Set JIRA_BASE_URL=https://<your-domain>.atlassian.net in .env",
                jira_base_url,
            )
            return {"tasks": []}

        jira_email = (os.environ.get("JIRA_EMAIL") or settings.jira_email or "").strip()
        jira_api_token = (os.environ.get("JIRA_API_TOKEN") or settings.jira_api_token or "").strip()
        jira_project_key = (os.environ.get("JIRA_PROJECT_KEY") or settings.jira_project_key or "").strip()

        server_params = StdioServerParameters(
            command="python",
            args=[_JIRA_MCP_PATH],
            env={
                **os.environ,
                "JIRA_BASE_URL": jira_base_url,
                "JIRA_EMAIL": jira_email,
                "JIRA_API_TOKEN": jira_api_token,
                "JIRA_PROJECT_KEY": jira_project_key,
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("Jira MCP connected")

                result = await session.call_tool(
                    "create_jira_tasks_bulk",
                    arguments={"tasks": bulk_tasks},
                )

                raw_result = "".join(
                    block.text
                    for block in (result.content or [])
                    if hasattr(block, "text") and block.text
                ).strip()

                if not raw_result:
                    logger.error("Jira MCP returned empty response")
                    return {"tasks": [], "error_log": ["Jira MCP empty response"]}

                raw_result = (
                    raw_result.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                )
                results = json.loads(raw_result)

                for r, task in zip(results, parsed_tasks):
                    if r.get("success"):
                        logger.info("Created: %s → %s", r["summary"], r["issue_key"])
                        created_tasks.append(
                            ExtractedTask(
                                assignee=task.get("assignee_name", "Unassigned"),
                                task_description=r["summary"],
                                deadline=task.get("due_date"),
                                priority=task.get("priority", "Medium").lower(),
                                is_ambiguous=False,
                                jira_ticket_url=r.get("url"),
                            )
                        )
                    else:
                        logger.warning(
                            "Failed to create '%s': %s", r.get("summary"), r.get("error")
                        )

    except Exception as exc:
        logger.warning("Jira MCP call failed (non-fatal): %s", exc)

    logger.info("Done. %d/%d tasks created in Jira.", len(created_tasks), len(parsed_tasks))
    return {"tasks": created_tasks}
