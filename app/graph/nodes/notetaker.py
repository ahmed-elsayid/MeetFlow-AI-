"""Notetaker agent — incremental note-taking during the meeting, full
summarisation + Notion write at end of meeting.

Live mode  (is_meeting_active=True):
  • Called once per relevant chunk.
  • Processes only the LATEST chunk (O(1) API calls, not O(N²)).
  • Updates state["notes"] and state["decisions"] incrementally.
  • Does NOT write to Notion yet.

Post-meeting mode  (is_meeting_active=False):
  • Processes the FULL accumulated transcript in batches.
  • Produces a clean, deduplicated final summary.
  • Writes the result to Notion.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.graph.nodes._llm import build_llm
from app.models.schemas import NoteSection

logger = logging.getLogger(__name__)

PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "notetaker.txt"
)
CHUNK_TOKEN_LIMIT = 3000
CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _chunk_transcript(transcript: str, max_tokens: int = CHUNK_TOKEN_LIMIT) -> list[str]:
    """Split a long transcript string into ~max_tokens batches."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    lines = transcript.split("\n")
    batches: list[str] = []
    current: list[str] = []
    current_len = 0
    overlap_lines = 4

    for line in lines:
        line_len = len(line)
        if current_len + line_len > max_chars and current:
            batches.append("\n".join(current))
            overlap = current[-overlap_lines:]
            current = overlap + [line]
            current_len = sum(len(l) for l in current)
        else:
            current.append(line)
            current_len += line_len

    if current:
        batches.append("\n".join(current))
    return batches


def _build_transcript_from_chunks(chunks: list) -> str:
    lines: list[str] = []
    for c in chunks:
        if hasattr(c, "speaker"):
            lines.append(f"[{c.speaker}]: {c.text}")
        elif isinstance(c, dict):
            lines.append(f"[{c.get('speaker', 'Unknown')}]: {c.get('text', '')}")
    return "\n".join(lines)


def _serialize_existing_notes(notes: list[NoteSection], decisions: list[str]) -> str:
    """Produce a compact text representation of accumulated notes for the LLM."""
    parts: list[str] = []
    for n in notes:
        obj = n if isinstance(n, NoteSection) else NoteSection(**n)
        points_text = "\n".join(f"  • {p}" for p in obj.points)
        parts.append(f"**{obj.topic}**\n{points_text}")
    if decisions:
        dec_text = "\n".join(f"  • {d}" for d in decisions)
        parts.append(f"**Decisions**\n{dec_text}")
    return "\n\n".join(parts)


async def _call_llm_for_notes(
    llm,
    prompt_template: str,
    existing_notes_str: str,
    chunks_text: str,
) -> tuple[list[NoteSection], list[str]]:
    """Single LLM call to the notetaker.txt template. Returns (sections, decisions)."""
    prompt = prompt_template.format(
        existing_notes=existing_notes_str or "(none yet)",
        chunks=chunks_text,
    )
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = (
        response.content.strip()
        .removeprefix("```json").removeprefix("```")
        .removesuffix("```").strip()
    )
    data = json.loads(raw)

    sections = [
        NoteSection(
            topic=s.get("topic", "Notes"),
            points=s.get("points", []),
            is_decision=s.get("is_decision", False),
        )
        for s in data.get("sections", [])
    ]
    decisions = data.get("decisions", [])
    return sections, decisions


async def _write_to_notion(
    meeting_id: str,
    all_sections: list[NoteSection],
    all_decisions: list[str],
) -> None:
    """Write the final accumulated notes to Notion via MCP stdio."""
    from mcp import StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.client.stdio import stdio_client

    try:
        from app.config import settings

        # Strip the view query param (?v=...) browsers append when copying Notion URLs.
        # Use settings object — pydantic-settings reads .env but does NOT write to os.environ.
        raw_db_id = (settings.notion_database_id or "").strip()
        database_id = raw_db_id.split("?")[0].strip()
        if not database_id:
            raise ValueError("NOTION_DATABASE_ID is not set in .env")

        if "-" not in database_id and len(database_id) == 32:
            database_id = (
                f"{database_id[0:8]}-{database_id[8:12]}-"
                f"{database_id[12:16]}-{database_id[16:20]}-{database_id[20:]}"
            )

        # Prefer OAuth token file; fall back to integration token in .env.
        token_path = Path(__file__).resolve().parent.parent.parent.parent / "notion_token.txt"
        if token_path.exists():
            notion_token = token_path.read_text(encoding="utf-8").strip()
            logger.info("Notion: using OAuth token from notion_token.txt")
        else:
            notion_token = (settings.notion_api_key or "").strip()
            if not notion_token:
                raise ValueError(
                    "No Notion token — set NOTION_API_KEY in .env "
                    "or complete OAuth flow (notion_token.txt)"
                )
            logger.info("Notion: using NOTION_API_KEY from .env")

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={
                "OPENAPI_MCP_HEADERS": json.dumps({
                    "Authorization": f"Bearer {notion_token}",
                    "Notion-Version": "2022-06-28",
                })
            },
        )

        children: list[dict] = []

        if all_decisions:
            children.append({
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Key Decisions"}}]},
            })
            for d in all_decisions:
                children.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": d}}]},
                })

        for section in all_sections:
            children.append({
                "type": "heading_2" if section.is_decision else "heading_3",
                "heading_2" if section.is_decision else "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": section.topic}}]
                },
            })
            for point in section.points:
                children.append({
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": point}}]},
                })

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.call_tool(
                    "API-post-page",
                    arguments={
                        "parent": {"database_id": database_id},
                        "properties": {
                            "title": {"title": [{"text": {"content": f"Meeting Notes – {meeting_id}"}}]}
                        },
                        "children": children,
                    },
                )
                logger.info("Notion page created for meeting %s", meeting_id)

    except Exception as exc:
        logger.warning("Notion MCP write failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

async def notetaker_node(state: dict) -> dict:
    """LangGraph node: incremental live note-taking or full post-meeting summarisation."""
    is_live: bool = state.get("is_meeting_active", True)
    chunks = state.get("chunks", [])

    if not chunks:
        return {}

    try:
        prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"Prompt file not found: {PROMPT_PATH}"
        logger.error(msg)
        return {"error_log": [msg]}

    llm = build_llm(max_tokens=2048, temperature=0)

    # Existing accumulated notes (for deduplication context)
    existing_sections: list[NoteSection] = state.get("notes", [])
    existing_decisions: list[str] = state.get("decisions", [])
    existing_notes_str = _serialize_existing_notes(existing_sections, existing_decisions)

    if is_live:
        # ---------------------------------------------------------------
        # LIVE MODE — process only the latest chunk (fast, O(1) per call)
        # ---------------------------------------------------------------
        latest = chunks[-1]
        if hasattr(latest, "speaker"):
            chunk_text = f"[{latest.speaker}]: {latest.text}"
        elif isinstance(latest, dict):
            chunk_text = f"[{latest.get('speaker', 'Unknown')}]: {latest.get('text', '')}"
        else:
            return {}

        try:
            new_sections, new_decisions = await _call_llm_for_notes(
                llm, prompt_template, existing_notes_str, chunk_text
            )
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Notetaker parse failed for live chunk: %s", exc)
            return {"error_log": [f"notetaker live parse error: {exc}"]}
        except Exception as exc:
            logger.warning("Notetaker LLM failed for live chunk: %s", exc)
            return {"error_log": [f"notetaker live error: {exc}"]}

        logger.info(
            "Live notetaker: +%d sections +%d decisions", len(new_sections), len(new_decisions)
        )
        return {"notes": new_sections, "decisions": new_decisions}

    else:
        # ---------------------------------------------------------------
        # POST-MEETING MODE — full transcript, batched, then Notion write
        # ---------------------------------------------------------------
        full_transcript = _build_transcript_from_chunks(chunks)
        if not full_transcript.strip():
            return {}

        batches = _chunk_transcript(full_transcript)
        logger.info("Post-meeting notetaker: processing %d batch(es)", len(batches))

        # Carry accumulated notes forward across batches
        running_sections: list[NoteSection] = list(existing_sections)
        running_decisions: list[str] = list(existing_decisions)

        for i, batch_text in enumerate(batches, start=1):
            running_str = _serialize_existing_notes(running_sections, running_decisions)
            try:
                new_secs, new_decs = await _call_llm_for_notes(
                    llm, prompt_template, running_str, batch_text
                )
                running_sections.extend(new_secs)
                running_decisions.extend(new_decs)
                logger.info("Batch %d/%d: +%d sections +%d decisions", i, len(batches), len(new_secs), len(new_decs))
            except (json.JSONDecodeError, TypeError) as exc:
                logger.warning("Notetaker batch %d parse failed: %s", i, exc)
            except Exception as exc:
                logger.warning("Notetaker batch %d LLM failed: %s", i, exc)

        # Slices that are NEW (not already in existing state — they're the delta to add)
        final_new_sections = running_sections[len(existing_sections):]
        final_new_decisions = running_decisions[len(existing_decisions):]

        meeting_id = state.get("meeting_id", "unknown")
        await _write_to_notion(meeting_id, running_sections, running_decisions)

        logger.info(
            "Post-meeting notetaker done: %d total sections, %d total decisions",
            len(running_sections), len(running_decisions),
        )
        return {"notes": final_new_sections, "decisions": final_new_decisions}
