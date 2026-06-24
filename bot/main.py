"""MeetFlow-AI Meeting Bot — CLI entry point.

Joins a Microsoft Teams meeting via a vision-guided browser approach
and scrapes real-time captions directly from the Teams web client.
No audio capture, no Whisper, no diarization — captions already
include speaker names.

Usage:
    python main.py --url "https://teams.microsoft.com/l/meetup-join/..."
    python main.py --meeting-id "123456" --passcode "abc"
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load variables from .env into os.environ
load_dotenv()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MeetFlow-AI Meeting Bot — Join Teams meetings and "
        "scrape real-time captions from the browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python main.py --url "https://teams.microsoft.com/l/meetup-join/..."
  python main.py --url "..." --output-dir ./my_meeting
        """,
    )

    # Meeting target
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--url",
        help="Full Microsoft Teams meeting URL",
    )
    group.add_argument(
        "--meeting-id",
        help="Teams meeting ID (use with --passcode)",
    )
    parser.add_argument(
        "--passcode",
        help="Meeting passcode (required with --meeting-id)",
    )

    # Options
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (overrides OUTPUT_DIR from .env)",
    )
    parser.add_argument(
        "--display-name",
        default=None,
        help="Bot display name (overrides BOT_DISPLAY_NAME from .env)",
    )

    args = parser.parse_args()

    if args.meeting_id and not args.passcode:
        parser.error("--passcode is required when using --meeting-id")

    return args


def _setup_logging(output_dir: Path) -> None:
    """Configure logging to bot.log (file) + stderr (console)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "bot.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # File handler — detailed with ISO timestamps
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    ))
    root.addHandler(fh)

    # Console handler — concise
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(ch)


def _build_meeting_url(meeting_id: str, passcode: str) -> str:
    """Construct a Teams meeting URL from meeting ID + passcode."""
    # Teams meeting URLs follow this pattern
    return (
        f"https://teams.microsoft.com/l/meetup-join/"
        f"{meeting_id}/0?context=%7b%22Tid%22%3a%22%22%7d"
        f"&passcode={passcode}"
    )


async def _async_main(args: argparse.Namespace) -> None:
    """Async entry point — sets up components and runs the bot."""
    logger = logging.getLogger(__name__)

    # Resolve configuration
    output_dir = args.output_dir or os.getenv("OUTPUT_DIR", "./output")
    display_name = args.display_name or os.getenv("BOT_DISPLAY_NAME", "Meeting Recorder")
    app_server_url = os.getenv("APP_SERVER_URL", "")

    # Build the meeting URL
    if args.url:
        meeting_url = args.url
    else:
        meeting_url = _build_meeting_url(args.meeting_id, args.passcode)

    logger.info("=" * 60)
    logger.info("  MeetFlow-AI Meeting Bot")
    logger.info("=" * 60)
    logger.info("  Meeting URL:   %s", meeting_url[:80] + "…")
    logger.info("  Display name:  %s", display_name)
    logger.info("  Output dir:    %s", Path(output_dir).resolve())
    logger.info("  Transcription: Browser caption scraping (no Whisper)")
    logger.info("  App server:    %s", app_server_url or "(not configured)")
    logger.info("=" * 60)

    # Shared shutdown event
    shutdown_event = asyncio.Event()

    # Initialize components
    logger.info("Initializing components …")

    from bot.joiner import TeamsJoiner
    from captions.captions import CaptionScraper
    from output.writer import TranscriptWriter
    import pipeline

    joiner = TeamsJoiner(
        display_name=display_name,
        shutdown_event=shutdown_event,
        output_dir=output_dir,
    )

    writer = TranscriptWriter(output_dir=output_dir)

    caption_queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    logger.info("All components initialized ✓")

    # Signal handling for Ctrl+C
    def _handle_signal(sig, frame):
        logger.info("Received signal %s — initiating graceful shutdown …", sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Phase 1: Join the meeting
    try:
        logger.info("Phase 1: Joining meeting …")
        await joiner._launch_browser()
        await joiner._join_meeting(meeting_url)

        if not joiner._joined:
            logger.error("Failed to join meeting — exiting")
            await joiner.leave()
            return

        logger.info("Phase 1 complete — in the meeting ✓")

        # Phase 2: Start caption scraping + stay-alive in parallel
        page = joiner.get_page()
        if page is None:
            logger.error("No browser page available — exiting")
            await joiner.leave()
            return

        scraper = CaptionScraper(
            page=page,
            shutdown_event=shutdown_event,
        )

        logger.info("Phase 2: Starting caption scraping …")

        tasks = [
            asyncio.create_task(
                joiner._stay_alive_loop(),
                name="stay_alive",
            ),
            asyncio.create_task(
                scraper.start(caption_queue),
                name="caption_scraper",
            ),
            asyncio.create_task(
                pipeline.run(
                    queue=caption_queue,
                    shutdown_event=shutdown_event,
                    writer=writer,
                    app_server_url=app_server_url or None,
                ),
                name="pipeline",
            ),
        ]

        # Wait for any task to finish (normally stay_alive signals shutdown)
        done, pending = await asyncio.wait(
            tasks, return_when=asyncio.FIRST_COMPLETED
        )

        # Check for exceptions in completed tasks
        for task in done:
            if task.exception():
                logger.error(
                    "Task '%s' failed: %s",
                    task.get_name(),
                    task.exception(),
                )

        # Signal shutdown for remaining tasks
        shutdown_event.set()

        # Give remaining tasks time to finish gracefully
        if pending:
            logger.info("Waiting for %d remaining tasks …", len(pending))
            await asyncio.wait(pending, timeout=15)

            # Cancel any that are still running
            for task in pending:
                if not task.done():
                    task.cancel()

    except Exception:
        logger.error("Fatal error in main loop", exc_info=True)
        shutdown_event.set()

    finally:
        # Always finalize
        logger.info("Finalizing transcript …")
        await writer.finalize()
        await joiner.leave()
        logger.info("Bot shutdown complete")


def main() -> None:
    """CLI entry point."""
    # Load .env from the bot/ directory
    env_path = Path(__file__).parent / ".env"
    load_dotenv(str(env_path))

    # Also try parent directory .env
    load_dotenv(str(Path(__file__).parent.parent / ".env"))

    args = _parse_args()

    output_dir = args.output_dir or os.getenv("OUTPUT_DIR", "./output")
    _setup_logging(Path(output_dir))

    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        print("\nInterrupted — check output directory for partial transcript.")
        sys.exit(1)


if __name__ == "__main__":
    main()
