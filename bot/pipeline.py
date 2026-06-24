"""Processing pipeline — reads caption segments from a queue and writes output.

Replaces the old audio → transcription → diarization pipeline with a
simple consumer that takes finalized caption segments (already containing
speaker names and text) from the CaptionScraper and writes them to disk.
"""

from __future__ import annotations

import asyncio
import logging

from output.writer import TranscriptWriter

logger = logging.getLogger(__name__)


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

    # Lazy-init httpx client only if we need to forward to app server
    http_client = None
    if app_server_url:
        try:
            import httpx
            http_client = httpx.AsyncClient(timeout=10.0)
            logger.info("Will forward captions to: %s", app_server_url)
        except ImportError:
            logger.warning("httpx not installed — caption forwarding disabled")

    try:
        while True:
            # Try to get a segment, but check shutdown regularly
            try:
                segment = await asyncio.wait_for(
                    queue.get(), timeout=2.0
                )
            except asyncio.TimeoutError:
                if shutdown_event.is_set() and queue.empty():
                    logger.info("Pipeline draining complete — shutting down")
                    break
                continue

            segments_processed += 1

            try:
                # Write to disk
                await writer.append(segment)

                # Forward to app server if configured
                if http_client and app_server_url:
                    await _forward_to_app_server(
                        http_client, app_server_url, segment
                    )

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


async def _forward_to_app_server(
    client,
    base_url: str,
    segment,
) -> None:
    """POST a caption segment to the app server's /meeting/chunk endpoint."""
    seg_dict = segment.to_dict() if hasattr(segment, "to_dict") else segment

    payload = {
        "meeting_id": "live",  # The app server can override this
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
                "App server returned %d: %s",
                resp.status_code,
                resp.text[:200],
            )
    except Exception:
        logger.debug("Failed to forward segment to app server", exc_info=True)
