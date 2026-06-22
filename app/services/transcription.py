from __future__ import annotations

import logging
from io import BytesIO

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import TranscriptChunk

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe_audio(
    audio_bytes: bytes,
    meeting_id: str,
    offset_seconds: float = 0.0,
) -> list[TranscriptChunk]:
    """Transcribe audio bytes using OpenAI Whisper and return transcript chunks."""
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.webm"

    response = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="verbose_json",
        timestamp_granularities=["segment"],
    )

    chunks: list[TranscriptChunk] = []

    for segment in response.segments or []:
        abs_start = offset_seconds + segment.start
        abs_end = offset_seconds + segment.end

        chunk = TranscriptChunk(
            meeting_id=meeting_id,
            speaker="Speaker",
            text=segment.text.strip(),
            timestamp_start=_seconds_to_timestamp(abs_start),
            timestamp_end=_seconds_to_timestamp(abs_end),
            minute=int(abs_start // 60),
        )
        chunks.append(chunk)

    return chunks


def _seconds_to_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"
