"""Real-time caption scraper for Microsoft Teams.

Enables Teams' built-in captions, watches for DOM changes using a
MutationObserver, extracts speaker names and finalized caption text,
and emits transcript segments onto an asyncio queue.

Based on the Recall.ai browser-automation approach:
  - Injects MutationObserver on the caption container
  - Detects finalized captions via terminal punctuation
  - Deduplicates partial caption updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import timedelta

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# ── How long to wait for captions to appear after enabling ──────────────────
CAPTIONS_ENABLE_TIMEOUT_SECONDS = 30

# ── JS injected into the Teams page ────────────────────────────────────────

ENABLE_CAPTIONS_SCRIPT = """
async () => {
    // Click the "More" (…) menu button, then look for "Turn on live captions"
    // Teams UI: the "More actions" button in the call bar
    const moreBtn = document.querySelector('[data-tid="callingButtons-showMoreBtn"]')
                 || document.querySelector('button[id="callingButtons-showMoreBtn"]');
    if (moreBtn) {
        moreBtn.click();
        await new Promise(r => setTimeout(r, 1500));
    }

    // Find and click "Turn on live captions" or "Live captions"
    const menuItems = document.querySelectorAll('[role="menuitem"], [role="menuitemcheckbox"]');
    for (const item of menuItems) {
        const text = item.textContent || '';
        if (text.toLowerCase().includes('live captions') ||
            text.toLowerCase().includes('turn on live captions') ||
            text.toLowerCase().includes('captions')) {
            item.click();
            await new Promise(r => setTimeout(r, 1000));
            return 'enabled';
        }
    }

    // Also try the captions button directly (some Teams versions)
    const captionsBtn = document.querySelector('[data-tid="toggle-captions"]')
                     || document.querySelector('button[id="captions-button"]');
    if (captionsBtn) {
        captionsBtn.click();
        await new Promise(r => setTimeout(r, 1000));
        return 'enabled';
    }

    return 'not_found';
}
"""

# This script sets up a MutationObserver on the captions container and
# stores incoming caption events in a global array that we poll from Python.
CAPTION_OBSERVER_SCRIPT = """
() => {
    // Prevent double-init
    if (window.__meetflow_caption_observer) return 'already_initialized';

    window.__meetflow_captions_buffer = [];
    window.__meetflow_caption_observer = true;

    // Find the captions wrapper — Teams uses this data-tid
    const findCaptionContainer = () => {
        return document.querySelector('div[data-tid="closed-caption-renderer-wrapper"]')
            || document.querySelector('[class*="captionsContainer"]')
            || document.querySelector('[class*="captions-container"]');
    };

    const setupObserver = (targetNode) => {
        const observer = new MutationObserver((mutationsList) => {
            for (const mutation of mutationsList) {
                if (mutation.type !== 'childList') continue;

                mutation.addedNodes.forEach((node) => {
                    if (!(node instanceof HTMLElement)) return;

                    // Look for the caption message element
                    const captionMessage = node.querySelector
                        ? (node.querySelector('.fui-ChatMessageCompact')
                           || node.querySelector('[class*="caption"]')
                           || node)
                        : null;
                    if (!captionMessage) return;

                    // Extract speaker name
                    const authorElement = captionMessage.querySelector('span[data-tid="author"]')
                        || captionMessage.querySelector('[class*="author"]')
                        || captionMessage.querySelector('[class*="speaker"]');
                    
                    if (!authorElement) return;
                    
                    const speaker = authorElement.textContent.trim();

                    // Extract caption text
                    const textElements = captionMessage.querySelectorAll('span:not([data-tid="author"])');
                    let text = '';
                    textElements.forEach(el => {
                        const t = el.textContent.trim();
                        if (t && t !== speaker) text += ' ' + t;
                    });
                    text = text.trim();

                    if (!text) {
                        // Fallback: grab all text content minus the speaker name
                        text = captionMessage.textContent.replace(speaker, '').trim();
                    }

                    if (text) {
                        window.__meetflow_captions_buffer.push({
                            speaker: speaker,
                            text: text,
                            timestamp: Date.now()
                        });
                    }

                    // Also watch for updates to this caption node
                    const textObserver = new MutationObserver(() => {
                        const updatedTextEls = captionMessage.querySelectorAll('span:not([data-tid="author"])');
                        let updatedText = '';
                        updatedTextEls.forEach(el => {
                            const t = el.textContent.trim();
                            if (t && t !== speaker) updatedText += ' ' + t;
                        });
                        updatedText = updatedText.trim();

                        if (!updatedText) {
                            updatedText = captionMessage.textContent.replace(speaker, '').trim();
                        }

                        if (updatedText) {
                            window.__meetflow_captions_buffer.push({
                                speaker: speaker,
                                text: updatedText,
                                timestamp: Date.now()
                            });
                        }
                    });

                    textObserver.observe(captionMessage, {
                        characterData: true,
                        childList: true,
                        subtree: true
                    });
                });
            }
        });

        observer.observe(targetNode, { childList: true, subtree: true });
        return true;
    };

    // Try to find and observe the container immediately
    let container = findCaptionContainer();
    if (container) {
        setupObserver(container);
        return 'initialized';
    }

    // If not found yet, watch for it to appear
    const bodyObserver = new MutationObserver(() => {
        const c = findCaptionContainer();
        if (c) {
            bodyObserver.disconnect();
            setupObserver(c);
        }
    });
    bodyObserver.observe(document.body, { childList: true, subtree: true });
    return 'waiting_for_container';
}
"""

# Script to drain the captions buffer from the browser
DRAIN_CAPTIONS_SCRIPT = """
() => {
    const buf = window.__meetflow_captions_buffer || [];
    window.__meetflow_captions_buffer = [];
    return JSON.stringify(buf);
}
"""


@dataclass
class CaptionEvent:
    """A single caption event from the browser."""

    speaker: str
    text: str
    timestamp_ms: int  # JS Date.now() value


@dataclass
class TranscriptSegment:
    """A finalized transcript segment ready for output."""

    speaker: str
    text: str
    start: float  # seconds since meeting start
    timestamp_human: str  # "HH:MM:SS"

    def to_dict(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start": round(self.start, 2),
            "end": round(self.start, 2),  # captions don't give end time
            "timestamp_human": self.timestamp_human,
        }


class CaptionScraper:
    """Scrapes real-time captions from the Microsoft Teams web client.

    After the bot has joined the meeting, call ``start()`` to enable
    captions and begin scraping.  Finalized caption segments are placed
    on the provided ``asyncio.Queue``.
    """

    def __init__(
        self,
        page: Page,
        shutdown_event: asyncio.Event,
        poll_interval: float = 0.5,
    ) -> None:
        self._page = page
        self._shutdown_event = shutdown_event
        self._poll_interval = poll_interval

        # State for finalization / dedup
        self._last_caption: dict | None = None  # {speaker, text}
        self._meeting_start_ms: int | None = None
        self._segments_emitted: int = 0

        # Terminal punctuation regex (signals a caption is finalized)
        self._terminal_re = re.compile(r"[.!?]$")
        # Regex to strip punctuation for dedup comparison
        self._punct_strip_re = re.compile(r"[.,;:'\"\-!~?]")

    async def start(self, queue: asyncio.Queue) -> None:
        """Enable captions and scrape them until shutdown.

        Each finalized caption is placed on *queue* as a ``TranscriptSegment``.
        """
        logger.info("Enabling Teams live captions …")
        await self._enable_captions()

        logger.info("Injecting MutationObserver for captions …")
        result = await self._page.evaluate(CAPTION_OBSERVER_SCRIPT)
        logger.info("Caption observer status: %s", result)

        # Record meeting start time
        self._meeting_start_ms = int(time.time() * 1000)

        logger.info(
            "Caption scraper started — polling every %.1fs",
            self._poll_interval,
        )

        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(self._poll_interval)
                raw = await self._page.evaluate(DRAIN_CAPTIONS_SCRIPT)
                events = json.loads(raw) if raw else []

                for evt in events:
                    caption = CaptionEvent(
                        speaker=evt.get("speaker", "Unknown"),
                        text=evt.get("text", ""),
                        timestamp_ms=evt.get("timestamp", 0),
                    )
                    segment = self._process_caption(caption)
                    if segment is not None:
                        await queue.put(segment)

            except Exception:
                if self._shutdown_event.is_set():
                    break
                logger.warning("Caption poll error", exc_info=True)
                await asyncio.sleep(2)

        logger.info(
            "Caption scraper stopped — %d segments emitted",
            self._segments_emitted,
        )

    async def _enable_captions(self) -> None:
        """Click the UI elements to turn on live captions."""
        for attempt in range(3):
            try:
                result = await self._page.evaluate(ENABLE_CAPTIONS_SCRIPT)
                logger.info(
                    "Enable captions attempt %d: %s", attempt + 1, result
                )
                if result == "enabled":
                    # Wait a moment for captions to start rendering
                    await asyncio.sleep(2)
                    return
            except Exception:
                logger.warning(
                    "Enable captions attempt %d failed", attempt + 1,
                    exc_info=True,
                )

            await asyncio.sleep(3)

        # Fallback: try keyboard shortcut (Ctrl+Shift+U in some Teams versions)
        logger.info("Trying keyboard shortcut to enable captions …")
        try:
            await self._page.keyboard.press("Control+Shift+u")
            await asyncio.sleep(2)
        except Exception:
            pass

        logger.warning(
            "Could not confirm captions were enabled — will attempt to "
            "scrape anyway (captions may already be on)"
        )

    def _process_caption(self, caption: CaptionEvent) -> TranscriptSegment | None:
        """Process a raw caption event and return a finalized segment or None.

        Applies two filters from the Recall.ai approach:
        1. Only emit captions that end with terminal punctuation (finalized)
        2. Deduplicate by comparing stripped text to the last emitted caption
        """
        text = caption.text.strip()
        if not text:
            return None

        # Filter 1: Wait for terminal punctuation (finalization signal)
        if not self._terminal_re.search(text):
            return None

        # Filter 2: Deduplicate against last emitted caption
        stripped_new = self._punct_strip_re.sub("", text).lower().strip()
        if self._last_caption is not None:
            stripped_last = self._punct_strip_re.sub(
                "", self._last_caption["text"]
            ).lower().strip()
            if stripped_new == stripped_last:
                return None

        # This is a finalized, non-duplicate caption — emit it
        self._last_caption = {"speaker": caption.speaker, "text": text}

        # Calculate relative time
        if self._meeting_start_ms and caption.timestamp_ms:
            elapsed_s = (caption.timestamp_ms - self._meeting_start_ms) / 1000.0
        else:
            elapsed_s = 0.0
        elapsed_s = max(0.0, elapsed_s)

        self._segments_emitted += 1
        segment = TranscriptSegment(
            speaker=caption.speaker,
            text=text,
            start=elapsed_s,
            timestamp_human=_format_timestamp(elapsed_s),
        )

        logger.info(
            "[%s] %s: %s",
            segment.timestamp_human,
            segment.speaker,
            segment.text[:80],
        )
        return segment


def _format_timestamp(seconds: float) -> str:
    """Convert seconds to HH:MM:SS string."""
    return str(timedelta(seconds=int(seconds)))
