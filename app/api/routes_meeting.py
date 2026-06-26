from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.graph.builder import build_live_graph, build_post_meeting_graph
from app.models.schemas import ChunkInput, EndMeetingRequest, MeetingStartRequest, TranscriptChunk
from app.persistence.hitl_store import delete_hitl_requests_for_meeting
from app.services.rag import get_rag_service
from app.services.redis_queue import delete_meeting_state, get_meeting_state, store_meeting_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["meeting"])

_active_meetings: dict[str, dict[str, Any]] = {}

live_graph = build_live_graph()
post_meeting_graph = build_post_meeting_graph()

# [H:MM:SS] Speaker Name: transcript text
_TRANSCRIPT_LINE_RE = re.compile(r"^\[(\d+:\d+:\d+)\]\s+(.+?):\s+(.+)$")


def _init_state(meeting_id: str) -> dict:
    return {
        "meeting_id": meeting_id,
        "chunks": [],
        "classified": [],
        "notes": [],
        "decisions": [],
        "action_items": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "recipient_emails": [],
        "stakeholder_emails": [],
        "error_log": [],
        "transcript": "",
    }


def _parse_timestamp_to_minute(ts: str) -> int:
    """Convert 'H:MM:SS' or 'MM:SS' to the minute number."""
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 2:
            return int(parts[0])
    except ValueError:
        pass
    return 0


def _parse_transcript_file(text: str, meeting_id: str) -> list[TranscriptChunk]:
    """Parse lines of the form '[H:MM:SS] Speaker: text' into TranscriptChunk objects."""
    chunks: list[TranscriptChunk] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        m = _TRANSCRIPT_LINE_RE.match(line)
        if not m:
            continue
        ts = m.group(1)
        speaker = m.group(2).strip()
        content = m.group(3).strip()
        if not content:
            continue
        chunks.append(
            TranscriptChunk(
                meeting_id=meeting_id,
                speaker=speaker,
                text=content,
                timestamp_start=ts,
                timestamp_end=ts,
                minute=_parse_timestamp_to_minute(ts),
                source_type="uploaded_transcript",
            )
        )
    return chunks


# ---------------------------------------------------------------------------
# Background helpers
# ---------------------------------------------------------------------------

async def _run_post_meeting(meeting_id: str, state: dict) -> None:
    """Run the post-meeting graph in the background and persist the result."""
    try:
        logger.info("Post-meeting processing started for %s", meeting_id)
        result = await post_meeting_graph.ainvoke(state)
        merged = dict(state)
        for key, value in result.items():
            merged[key] = value
        await store_meeting_state(meeting_id, merged)
        logger.info("Post-meeting processing complete for %s", meeting_id)
    except Exception:
        logger.exception("Post-meeting processing failed for %s", meeting_id)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@router.post("/start")
async def start_meeting(req: MeetingStartRequest):
    if req.meeting_id in _active_meetings:
        raise HTTPException(400, "Meeting already active")

    state = _init_state(req.meeting_id)
    _active_meetings[req.meeting_id] = {
        "state": state,
        "title": req.title,
        "participants": req.participants,
    }

    await store_meeting_state(req.meeting_id, state)
    logger.info("Meeting started: %s", req.meeting_id)

    return {"status": "started", "meeting_id": req.meeting_id}


@router.post("/upload-transcript")
async def upload_transcript(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    meeting_id: str = Form(...),
    title: str = Form(""),
    recipient_emails: str = Form(""),
    stakeholder_emails: str = Form(""),
):
    """Parse a .txt transcript file, embed into RAG, then run post-meeting processing.

    Expected format (one line per utterance):
        [H:MM:SS] Speaker Name: transcript text

    Returns immediately; analysis (notes, tasks, emails) runs in the background.
    """
    if meeting_id in _active_meetings:
        raise HTTPException(400, "A meeting with this ID is already active")

    raw_text = (await file.read()).decode("utf-8", errors="replace")
    chunks = _parse_transcript_file(raw_text, meeting_id)

    if not chunks:
        raise HTTPException(
            400,
            "No transcript lines found. Expected format: [H:MM:SS] Speaker: text",
        )

    # Build meeting state
    recipients = [e.strip() for e in recipient_emails.split(",") if e.strip()]
    stakeholders = [e.strip() for e in stakeholder_emails.split(",") if e.strip()] or recipients

    state = _init_state(meeting_id)
    state["is_meeting_active"] = False
    state["chunks"] = [c.model_dump() for c in chunks]
    state["transcript"] = "\n".join(
        f"[{c.speaker} at {c.timestamp_start}]: {c.text}" for c in chunks
    )
    state["recipient_emails"] = recipients
    state["stakeholder_emails"] = stakeholders

    # Register as an active meeting so the UI picks it up
    _active_meetings[meeting_id] = {
        "state": state,
        "title": title or meeting_id,
        "participants": recipients,
    }
    await store_meeting_state(meeting_id, state)

    # Embed every chunk into ChromaDB for RAG search
    rag = get_rag_service()
    embedded = 0
    for chunk in chunks:
        try:
            await rag.embed_and_store(chunk)
            embedded += 1
        except Exception:
            logger.warning(
                "Failed to embed chunk [%s] for meeting %s",
                chunk.timestamp_start, meeting_id,
            )

    logger.info(
        "Transcript uploaded: meeting=%s chunks=%d embedded=%d",
        meeting_id, len(chunks), embedded,
    )

    # Run notes + email generation in the background
    background_tasks.add_task(_run_post_meeting, meeting_id, state)

    return {
        "status": "processing",
        "meeting_id": meeting_id,
        "chunks_parsed": len(chunks),
        "chunks_embedded": embedded,
        "message": (
            "Transcript uploaded and embedded. "
            "Note-taking, task extraction, and email drafting are running in the background."
        ),
    }


@router.post("/chunk")
async def process_chunk(chunk_input: ChunkInput):
    meeting = _active_meetings.get(chunk_input.meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found. Call /meeting/start first.")

    chunk = TranscriptChunk(
        meeting_id=chunk_input.meeting_id,
        speaker=chunk_input.speaker,
        text=chunk_input.text,
        timestamp_start=chunk_input.timestamp_start,
        timestamp_end=chunk_input.timestamp_end,
        minute=chunk_input.minute,
    )

    # Embed this chunk into ChromaDB so the researcher can find it via RAG
    try:
        await get_rag_service().embed_and_store(chunk)
    except Exception:
        logger.warning("Failed to embed chunk for meeting %s", chunk_input.meeting_id)

    # Accumulate chunk as a plain dict BEFORE running the graph.
    chunk_dict = chunk.model_dump()
    meeting["state"].setdefault("chunks", [])
    meeting["state"]["chunks"] = meeting["state"]["chunks"] + [chunk_dict]

    # Pass only the new TranscriptChunk object so classify_node gets a typed object.
    input_state = {**meeting["state"], "chunks": [chunk]}

    try:
        result = await live_graph.ainvoke(input_state)

        # Merge everything the graph produced EXCEPT chunks
        for key in meeting["state"]:
            if key == "chunks":
                continue
            if key in result and isinstance(result[key], list):
                meeting["state"][key] = result[key]
            elif key in result:
                meeting["state"][key] = result[key]

        await store_meeting_state(chunk_input.meeting_id, meeting["state"])
    except Exception:
        logger.exception("Error processing chunk for meeting %s", chunk_input.meeting_id)
        raise HTTPException(500, "Failed to process chunk")

    classified = meeting["state"].get("classified", [])
    if classified:
        last = classified[-1]
        latest_class = (
            last.classification if hasattr(last, "classification")
            else last.get("classification", "unknown") if isinstance(last, dict)
            else "unknown"
        )
    else:
        latest_class = "unknown"

    return {
        "status": "processed",
        "classification": latest_class,
        "notes_count": len(meeting["state"].get("notes", [])),
        "tasks_count": len(meeting["state"].get("tasks", [])),
    }


@router.post("/{meeting_id}/end")
async def end_meeting(
    meeting_id: str,
    background_tasks: BackgroundTasks,
    req: EndMeetingRequest = EndMeetingRequest(),
):
    meeting = _active_meetings.get(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    # Snapshot state for background task before removing from active dict
    state = dict(meeting["state"])
    state["is_meeting_active"] = False
    state["recipient_emails"] = req.recipient_emails
    state["stakeholder_emails"] = req.stakeholder_emails or req.recipient_emails

    summary = {
        "meeting_id": meeting_id,
        "total_chunks": len(state.get("chunks", [])),
        "notes_sections": len(state.get("notes", [])),
        "decisions": state.get("decisions", []),
        "tasks": len(state.get("tasks", [])),
        "research_briefs": len(state.get("research", [])),
        "email_drafts": len(state.get("email_drafts", [])),
        "errors": state.get("error_log", []),
    }

    # Remove from active meetings immediately so the response goes out right away
    del _active_meetings[meeting_id]
    logger.info("Meeting ended: %s — post-meeting analysis starting in background", meeting_id)

    # Post-meeting graph (notetaker → email_drafter → email_sender with HITL) runs in background.
    # This prevents the HTTP response from blocking on the 600-second HITL timeout.
    background_tasks.add_task(_run_post_meeting, meeting_id, state)

    return {"status": "ended", "summary": summary}


@router.get("/{meeting_id}/stream")
async def stream_meeting_chunks(meeting_id: str):
    """SSE endpoint — pushes new transcript chunks as they arrive (1 s poll)."""
    async def generator():
        last_count = 0
        while True:
            meeting = _active_meetings.get(meeting_id)
            if not meeting:
                yield "data: [DONE]\n\n"
                break
            chunks = meeting["state"].get("chunks", [])
            if len(chunks) > last_count:
                for chunk in chunks[last_count:]:
                    payload = json.dumps(_serialise_chunk(chunk))
                    yield f"data: {payload}\n\n"
                last_count = len(chunks)
            await asyncio.sleep(1)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting and all associated data (Redis, ChromaDB, SQLite HITL)."""
    _active_meetings.pop(meeting_id, None)

    await delete_meeting_state(meeting_id)

    rag = get_rag_service()
    deleted_chunks = await rag.delete_by_meeting(meeting_id)

    deleted_hitl = await delete_hitl_requests_for_meeting(meeting_id)

    logger.info(
        "Deleted meeting %s — %d embeddings, %d HITL records",
        meeting_id, deleted_chunks, deleted_hitl,
    )
    return {
        "status": "deleted",
        "meeting_id": meeting_id,
        "deleted_chunks": deleted_chunks,
        "deleted_hitl_records": deleted_hitl,
    }


def _serialise_chunk(c) -> dict:
    if hasattr(c, "model_dump"):
        return c.model_dump()
    if isinstance(c, dict):
        return c
    return {"text": str(c)}


def _serialise_list(items: list) -> list:
    out = []
    for item in items:
        if hasattr(item, "model_dump"):
            out.append(item.model_dump())
        elif isinstance(item, dict):
            out.append(item)
        else:
            out.append({"value": str(item)})
    return out


@router.get("/{meeting_id}/status")
async def meeting_status(meeting_id: str):
    meeting = _active_meetings.get(meeting_id)
    if not meeting:
        stored = await get_meeting_state(meeting_id)
        if stored:
            return {"status": "archived", "state": stored}
        raise HTTPException(404, "Meeting not found")

    state = meeting["state"]
    chunks = state.get("chunks", [])
    notes = state.get("notes", [])
    tasks = state.get("tasks", [])
    research = state.get("research", [])

    return {
        "status": "active" if state.get("is_meeting_active") else "ended",
        "chunks_processed": len(chunks),
        "notes_sections": len(notes),
        "tasks_extracted": len(tasks),
        "research_briefs": len(research),
        "pending_approvals": len(state.get("pending_approvals", [])),
        "errors": len(state.get("error_log", [])),
        "transcript": [_serialise_chunk(c) for c in chunks],
        "notes": _serialise_list(notes),
        "decisions": state.get("decisions", []),
        "tasks": _serialise_list(tasks),
        "research": _serialise_list(research),
    }
