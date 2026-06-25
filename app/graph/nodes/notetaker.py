"""Notetaker agent node — LLM summarizes transcript in chunks,
then merges results and writes to Notion via MCP stdio transport."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from mcp.client.stdio import stdio_client
from mcp import StdioServerParameters
from mcp.client.session import ClientSession

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "notetaker.txt"
CHUNK_TOKEN_LIMIT = 3000
CHARS_PER_TOKEN = 4  # rough estimate: 1 token ≈ 4 chars


def chunk_transcript(transcript: str, max_tokens: int = CHUNK_TOKEN_LIMIT, overlap_lines: int = 5) -> list[str]:
    """Split transcript into chunks of ~max_tokens each with overlapping lines at boundaries."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    lines = transcript.split("\n")
    chunks = []
    current_chunk = []
    current_len = 0
 
    for line in lines:
        line_len = len(line)
        if current_len + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            # carry over last `overlap_lines` lines into the next chunk
            overlap = current_chunk[-overlap_lines:]
            current_chunk = overlap + [line]
            current_len = sum(len(l) for l in current_chunk)
        else:
            current_chunk.append(line)
            current_len += line_len
 
    if current_chunk:
        chunks.append("\n".join(current_chunk))
 
    return chunks
 


def merge_summaries(summaries: list[dict]) -> dict:
    """Merge multiple chunk summaries into one final summary."""
    merged_decisions = []
    merged_actions = []
    merged_discussion = []
    seen_decisions = set()
    seen_actions = set()
    seen_headers = {}

    for summary in summaries:
        for d in summary.get("key_decisions", []):
            if d.lower() not in seen_decisions:
                seen_decisions.add(d.lower())
                merged_decisions.append(d)

        for a in summary.get("action_items", []):
            if a.lower() not in seen_actions:
                seen_actions.add(a.lower())
                merged_actions.append(a)

        for section in summary.get("discussion_points", []):
            header = section.get("header", "")
            notes = section.get("notes", [])
            if header in seen_headers:
                existing_notes = seen_headers[header]
                for note in notes:
                    if note not in existing_notes:
                        existing_notes.append(note)
            else:
                seen_headers[header] = list(notes)
                merged_discussion.append({"header": header, "notes": seen_headers[header]})

    return {
        "key_decisions": merged_decisions,
        "action_items": merged_actions,
        "discussion_points": merged_discussion,
    }


async def summarize_chunk(llm: ChatGroq, prompt_template: str, chunk: str, chunk_idx: int) -> dict:
    """Send a single chunk to the LLM and return parsed JSON."""
    response = llm.invoke([
        HumanMessage(content=prompt_template.replace("{transcript}", chunk))
    ])
    raw = response.content
    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(clean)
    logger.info("Chunk %d summarized: %d decisions, %d actions, %d topics",
                chunk_idx,
                len(data.get("key_decisions", [])),
                len(data.get("action_items", [])),
                len(data.get("discussion_points", [])))
    return data


async def notetaker_node(state: dict) -> dict:
    """LangGraph node: LLM summarizes transcript in chunks, then writes to Notion via MCP."""

    transcript = state.get("transcript", "")
    if not transcript:
        logger.info("Notetaker: empty transcript.")
        return {"notes": {}}

    if isinstance(transcript, list):
        transcript = "\n".join(
            f"{entry['speaker']['name']}: {entry['text']}"
            for entry in transcript
        )
    transcript = transcript.strip()

    total_tokens = len(transcript) // CHARS_PER_TOKEN
    logger.info("Transcript length: %d chars (~%d tokens)", len(transcript), total_tokens)

    # ------------------------------------------------------------------ #
    #  1. Load prompt
    # ------------------------------------------------------------------ #
    try:
        prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        msg = f"Prompt file not found: {PROMPT_PATH}"
        logger.error(msg)
        return {"error_log": [msg]}

    # ------------------------------------------------------------------ #
    #  2. Chunk + summarize each chunk
    # ------------------------------------------------------------------ #
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.getenv("GROQ_API_KEY")
    )

    chunks = chunk_transcript(transcript)
    logger.info("Split into %d chunks", len(chunks))

    summaries = []
    for i, chunk in enumerate(chunks):
        chunk_tokens = len(chunk) // CHARS_PER_TOKEN
        logger.info("Processing chunk %d/%d (~%d tokens)", i + 1, len(chunks), chunk_tokens)
        try:
            summary = await summarize_chunk(llm, prompt_template, chunk, i + 1)
            summaries.append(summary)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Failed to parse chunk %d: %s", i + 1, exc)
            continue
        except Exception as exc:
            logger.error("LLM call failed for chunk %d: %s", i + 1, exc)
            continue

    if not summaries:
        return {"error_log": ["All chunks failed to summarize"]}

    # ------------------------------------------------------------------ #
    #  3. Merge all chunk summaries
    # ------------------------------------------------------------------ #
    merged = merge_summaries(summaries)

    logger.info("Merged: %d decisions, %d actions, %d topics",
                len(merged["key_decisions"]),
                len(merged["action_items"]),
                len(merged["discussion_points"]))

    # ------------------------------------------------------------------ #
    #  3.5. LLM finalization — clean up, deduplicate, and coherence pass
    # ------------------------------------------------------------------ #
    final_prompt = f"""You are a meeting notes assistant.
Below are combined meeting notes extracted from multiple transcript chunks.
Clean them up: remove any duplicates, fix inconsistencies, and ensure the final output is coherent.
Return ONLY valid JSON, no markdown, no backticks.
{{
  "key_decisions": [...],
  "action_items": [...],
  "discussion_points": [...]
}}
Combined notes:
{json.dumps(merged, indent=2)}
"""

    try:
        response = llm.invoke([HumanMessage(content=final_prompt)])
        raw = response.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        final = json.loads(raw)
        logger.info("Finalized: %d decisions, %d actions, %d topics",
                    len(final.get("key_decisions", [])),
                    len(final.get("action_items", [])),
                    len(final.get("discussion_points", [])))
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("LLM finalization parse failed, falling back to merged: %s", exc)
        final = merged
    except Exception as exc:
        logger.warning("LLM finalization call failed, falling back to merged: %s", exc)
        final = merged

    key_decisions = final.get("key_decisions", merged["key_decisions"])
    action_items = final.get("action_items", merged["action_items"])
    discussion_points = final.get("discussion_points", merged["discussion_points"])

    # ------------------------------------------------------------------ #
    #  4. Write to Notion via MCP stdio
    # ------------------------------------------------------------------ #
    try:
        meeting_id = state["meeting_id"]
        database_id = os.environ["NOTION_DATABASE_ID"]
        if "-" not in database_id:
            database_id = f"{database_id[0:8]}-{database_id[8:12]}-{database_id[12:16]}-{database_id[16:20]}-{database_id[20:]}"

        with open("notion_token.txt") as f:
            notion_token = f.read().strip()

        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={"OPENAPI_MCP_HEADERS": f'{{"Authorization": "Bearer {notion_token}", "Notion-Version": "2022-06-28"}}'}
        )

        children = []

        children.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📋 Key Decisions Made"}}]}})
        for d in key_decisions:
            children.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": d}}]}})

        children.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "✅ Action Items"}}]}})
        for a in action_items:
            children.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": a}}]}})

        children.append({"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "📌 Main Discussion Points"}}]}})
        for section in discussion_points:
            children.append({"type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": section["header"]}}]}})
            for note in section["notes"]:
                children.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": note}}]}})

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("Notion MCP connected successfully")

                result = await session.call_tool(
                    "API-post-page",
                    arguments={
                        "parent": {"database_id": database_id},
                        "properties": {
                            "title": {"title": [{"text": {"content": f"Meeting Notes – {meeting_id}"}}]}
                        },
                        "children": children
                    }
                )
                logger.info("Notion page created: %s", result)

    except Exception as exc:
        import traceback
        logger.warning("Notion MCP push failed (non-fatal): %s", exc)
        traceback.print_exc()

    return {
        "notes": {
            "key_decisions": key_decisions,
            "action_items": action_items,
            "discussion_points": discussion_points,
        }
    }



