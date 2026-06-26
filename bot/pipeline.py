"""Processing pipeline — reads caption segments from a queue and writes output.

Replaces the old audio → transcription → diarization pipeline with a
simple consumer that takes finalized caption segments (already containing
speaker names and text) from the CaptionScraper and writes them to disk.
"""

from __future__ import annotations

import asyncio
import logging
import os

from output.writer import TranscriptWriter

logger = logging.getLogger(__name__)

# Configurable meeting ID — set APP_MEETING_ID in the bot's .env or environment.
# Defaults to "live" so the bot works out of the box if the app server has
# pre-registered a meeting with that ID.
_MEETING_ID = os.getenv("APP_MEETING_ID", "live")


async def _ensure_meeting_started(client, base_url: str, meeting_id: str) -> bool:
    """Call POST /meeting/start if the meeting isn't registered yet.

    Returns True if the meeting is now active, False on failure.
    """
    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/meeting/start",
            json={"meeting_id": meeting_id, "title": f"Meeting {meeting_id}"},
            timeout=10.0,
        )
        if resp.status_code in (200, 400):  # 400 = already active — that's fine
            logger.info("Meeting '%s' active on app server", meeting_id)
            return True
        logger.warning("Unexpected status from /meeting/start: %d", resp.status_code)
        return False
    except Exception as exc:
        logger.warning("Could not register meeting with app server: %s", exc)
        return False


async def run(
    queue: asyncio.Queue,
    shutdown_event: asyncio.Event,
    writer: TranscriptWriter,
    app_server_url: str | None = None,
) -> None:
    """Main pipeline loop.

    Reads TranscriptSegment objects from *queue* (produced by the
    CaptionScraper), writes them to the transcript files, and optionally
    forwards them to the app server via HTTP.

    Continues until *shutdown_event* is set and the queue is drained.
    """
    segments_processed = 0
    logger.info("Pipeline started — waiting for caption segments …")

    http_client = None
    if app_server_url:
        try:
            import httpx
            http_client = httpx.AsyncClient(timeout=10.0)
            logger.info("Will forward captions to: %s  (meeting_id=%s)", app_server_url, _MEETING_ID)
            # Auto-register the meeting so /meeting/chunk doesn't 404
            await _ensure_meeting_started(http_client, app_server_url, _MEETING_ID)
        except ImportError:
            logger.warning("httpx not installed — caption forwarding disabled")

    try:
        while True:
            try:
                segment = await asyncio.wait_for(queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if shutdown_event.is_set() and queue.empty():
                    logger.info("Pipeline draining complete — shutting down")
                    break
                continue

            segments_processed += 1

            try:
                await writer.append(segment)

                if http_client and app_server_url:
                    await _forward_to_app_server(http_client, app_server_url, segment)

            except Exception:
                logger.error(
                    "Error processing segment %d — skipping",
                    segments_processed,
                    exc_info=True,
                )
                continue

    finally:
        if http_client:
            await http_client.aclose()

    logger.info("Pipeline finished — %d segments processed", segments_processed)


async def _forward_to_app_server(client, base_url: str, segment) -> None:
    """POST a caption segment to the app server's /meeting/chunk endpoint."""
    seg_dict = segment.to_dict() if hasattr(segment, "to_dict") else segment

    payload = {
        "meeting_id": _MEETING_ID,
        "speaker": seg_dict.get("speaker", "Unknown"),
        "text": seg_dict.get("text", ""),
        "timestamp_start": seg_dict.get("timestamp_human", "00:00:00"),
        "timestamp_end": seg_dict.get("timestamp_human", "00:00:00"),
        "minute": int(seg_dict.get("start", 0) // 60),
    }

    try:
        resp = await client.post(
            f"{base_url.rstrip('/')}/meeting/chunk",
            json=payload,
        )
        if resp.status_code != 200:
            logger.warning(
                "App server returned %d: %s", resp.status_code, resp.text[:200]
            )
    except Exception:
        logger.debug("Failed to forward segment to app server", exc_info=True)
