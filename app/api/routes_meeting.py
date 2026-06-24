from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.graph.builder import build_live_graph, build_post_meeting_graph
from app.models.schemas import ChunkInput, EndMeetingRequest, MeetingStartRequest, TranscriptChunk
from app.services.redis_queue import get_meeting_state, store_meeting_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/meeting", tags=["meeting"])

_active_meetings: dict[str, dict[str, Any]] = {}

live_graph = build_live_graph()
post_meeting_graph = build_post_meeting_graph()


def _init_state(meeting_id: str) -> dict:
    return {
        "meeting_id": meeting_id,
        "chunks": [],
        "classified": [],
        "notes": [],
        "decisions": [],
        "tasks": [],
        "research": [],
        "email_drafts": [],
        "pending_approvals": [],
        "is_meeting_active": True,
        "recipient_emails": [],
        "stakeholder_emails": [],
        "error_log": [],
    }


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

    input_state = {**meeting["state"], "chunks": [chunk]}

    try:
        result = await live_graph.ainvoke(input_state)

        for key in meeting["state"]:
            if key in result and isinstance(result[key], list):
                meeting["state"][key] = result[key]
            elif key in result:
                meeting["state"][key] = result[key]

        await store_meeting_state(chunk_input.meeting_id, meeting["state"])
    except Exception:
        logger.exception("Error processing chunk for meeting %s", chunk_input.meeting_id)
        raise HTTPException(500, "Failed to process chunk")

    classified = meeting["state"].get("classified", [])
    latest_class = classified[-1].classification if classified else "unknown"

    return {
        "status": "processed",
        "classification": latest_class,
        "notes_count": len(meeting["state"].get("notes", [])),
        "tasks_count": len(meeting["state"].get("tasks", [])),
    }


@router.post("/{meeting_id}/end")
async def end_meeting(meeting_id: str, req: EndMeetingRequest = EndMeetingRequest()):
    meeting = _active_meetings.get(meeting_id)
    if not meeting:
        raise HTTPException(404, "Meeting not found")

    meeting["state"]["is_meeting_active"] = False
    meeting["state"]["recipient_emails"] = req.recipient_emails
    meeting["state"]["stakeholder_emails"] = req.stakeholder_emails or req.recipient_emails

    try:
        result = await post_meeting_graph.ainvoke(meeting["state"])

        for key in meeting["state"]:
            if key in result and isinstance(result[key], list):
                meeting["state"][key] = result[key]
            elif key in result:
                meeting["state"][key] = result[key]

        await store_meeting_state(meeting_id, meeting["state"])
    except Exception:
        logger.exception("Error in post-meeting processing for %s", meeting_id)

    summary = {
        "meeting_id": meeting_id,
        "total_chunks": len(meeting["state"].get("chunks", [])),
        "notes_sections": len(meeting["state"].get("notes", [])),
        "decisions": meeting["state"].get("decisions", []),
        "tasks": len(meeting["state"].get("tasks", [])),
        "research_briefs": len(meeting["state"].get("research", [])),
        "email_drafts": len(meeting["state"].get("email_drafts", [])),
        "errors": meeting["state"].get("error_log", []),
    }

    del _active_meetings[meeting_id]
    logger.info("Meeting ended: %s", meeting_id)

    return {"status": "ended", "summary": summary}


@router.get("/{meeting_id}/status")
async def meeting_status(meeting_id: str):
    meeting = _active_meetings.get(meeting_id)
    if not meeting:
        stored = await get_meeting_state(meeting_id)
        if stored:
            return {"status": "archived", "state": stored}
        raise HTTPException(404, "Meeting not found")

    state = meeting["state"]
    return {
        "status": "active" if state.get("is_meeting_active") else "ended",
        "chunks_processed": len(state.get("chunks", [])),
        "notes_sections": len(state.get("notes", [])),
        "tasks_extracted": len(state.get("tasks", [])),
        "research_briefs": len(state.get("research", [])),
        "pending_approvals": len(state.get("pending_approvals", [])),
        "errors": len(state.get("error_log", [])),
    }
