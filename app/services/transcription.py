from __future__ import annotations

import logging

from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)


def caption_to_chunks(
    speaker: str,
    text: str,
    meeting_id: str,
    timestamp_start: str = "00:00:00",
    timestamp_end: str = "00:00:00",
    minute: int = 0,
) -> list[TranscriptChunk]:
    """Convert a caption payload (already text) into TranscriptChunk objects.

    With the browser caption scraping approach, audio is never sent to
    this server — the bot scrapes captions directly from the Teams DOM
    and forwards them as text.  This function is a thin adapter that
    wraps the incoming text into the TranscriptChunk schema expected by
    the rest of the pipeline.
    """
    chunk = TranscriptChunk(
        meeting_id=meeting_id,
        speaker=speaker,
        text=text.strip(),
        timestamp_start=timestamp_start,
        timestamp_end=timestamp_end,
        minute=minute,
    )
    return [chunk]
