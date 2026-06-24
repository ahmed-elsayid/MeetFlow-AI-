"""Vision-guided Teams meeting joiner using Groq + Playwright.

Uses a Groq vision model to analyze browser screenshots and decide
what to click, making the join flow resilient to Teams UI changes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import platform
import re
import subprocess
import time
from pathlib import Path

from groq import Groq

logger = logging.getLogger(__name__)

# ── Groq vision prompt for the join phase ──────────────────────────────────

JOIN_PROMPT = """You are controlling a browser to join a Microsoft Teams meeting.
Look at this screenshot and tell me what action to take next.

Possible states and what to do:
- Pre-join / lobby screen with a "Join now" or "Join meeting" button → click it
- Name entry field asking for your name → type the bot's display name into the field
- "Use web app instead" or "Continue on this browser" link → click it
- "Open Microsoft Teams?" browser dialog → click Cancel or Stay on web
- Camera/mic permission popup → click Allow or dismiss it
- Toggle to turn OFF camera and/or microphone before joining → turn them off
- Already inside the meeting (can see participant list, meeting timer, meeting controls, chat, or people's avatars/video feeds) → respond with JOINED
- Meeting has ended (shows "The meeting has ended" or similar) → respond with ENDED
- Any other unexpected popup or dialog → describe it and suggest clicking to dismiss it

IMPORTANT: For 'click' actions, the 'description' MUST be the exact literal text on the button or link (e.g., "Join now", "Continue on this browser"). Do not add any extra descriptive words.

Respond ONLY with valid JSON, no explanation, no markdown:
{"action": "click", "description": "Join now"}
{"action": "type", "description": "name entry field", "text": "Meeting Recorder"}
{"action": "wait", "description": "page is loading"}
{"action": "JOINED", "description": "inside the meeting"}
{"action": "ENDED", "description": "meeting has ended"}
{"action": "dismiss", "description": "browser open-app dialog"}"""

# ── DOM change detection script injected into the page ─────────────────────

MUTATION_OBSERVER_SCRIPT = """
() => {
    if (window.__meetflow_observer) return;
    window.__teams_dom_changed = false;
    const observer = new MutationObserver((mutations) => {
        for (const m of mutations) {
            if (m.addedNodes.length > 0 || m.removedNodes.length > 0) {
                window.__teams_dom_changed = true;
                break;
            }
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    window.__meetflow_observer = true;
}
"""

JOIN_TIMEOUT_SECONDS = 300  # 5 minutes


class TeamsJoiner:
    """Vision-guided Microsoft Teams meeting joiner.

    Launches a Chromium browser via Playwright, navigates to the Teams
    meeting URL, and uses Groq's vision model to read screenshots and
    decide what to click.  After joining, monitors for meeting-end.
    """

    def __init__(
        self,
        display_name: str,
        shutdown_event: asyncio.Event,
        output_dir: str = "./output",
    ) -> None:
        self.display_name = display_name
        self.shutdown_event = shutdown_event
        self.output_dir = Path(output_dir)

        # Groq client
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        self.groq = Groq(api_key=api_key)
        self.vision_model = os.getenv(
            "GROQ_VISION_MODEL",
            "meta-llama/llama-4-scout-17b-16e-instruct",
        )

        # State
        self._joined = False
        self._ended = False
        self._browser = None
        self._page = None
        self._playwright = None

    # ── Public API ─────────────────────────────────────────────────────

    def get_page(self) -> "Page | None":
        """Return the Playwright page for use by the caption scraper."""
        return self._page


    async def join_and_stay(self, url: str) -> None:
        """Join the Teams meeting at *url* and stay until it ends."""
        await self._launch_browser()
        try:
            await self._join_meeting(url)
            if self._joined and not self._ended:
                await self._stay_alive_loop()
        finally:
            await self.leave()

    async def leave(self) -> None:
        """Close the browser and clean up."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            logger.debug("Browser cleanup error (non-fatal)", exc_info=True)
        self._browser = None
        self._page = None

    def is_active(self) -> bool:
        return self._joined and not self._ended

    # ── Browser launch ─────────────────────────────────────────────────

    async def _launch_browser(self) -> None:
        """Start Playwright Chromium with media-stream flags."""
        # On Linux, start Xvfb for headless rendering
        if platform.system() == "Linux":
            try:
                subprocess.Popen(
                    ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                os.environ["DISPLAY"] = ":99"
                logger.info("Xvfb started on display :99")
            except FileNotFoundError:
                logger.warning("Xvfb not found — assuming display is available")
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )
        # Lock user agent to Chrome 125 for consistent Teams DOM
        context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            permissions=[],
        )
        self._page = await context.new_page()
        logger.info("Chromium browser launched (user agent locked to Chrome 125)")

    # ── Vision-guided join ─────────────────────────────────────────────

    async def _join_meeting(self, url: str) -> None:
        """Attempt to join using fast static automation, fallback to vision."""
        try:
            await self._join_meeting_static(url)
        except Exception as e:
            logger.warning("Static automation failed, falling back to Groq Vision: %s", e)
            await self._join_meeting_vision(url)

    async def _join_meeting_static(self, url: str) -> None:
        """Navigate to the meeting URL and use Playwright DOM locators to join."""
        page = self._page
        logger.info("[Static] Navigating to Teams meeting URL …")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # 0. Teams.live.com specific: Click "Join now" on the landing page if it exists
        try:
            logger.info("[Static] Checking for initial 'Join now' or 'Join on the web' …")
            join_btn = page.get_by_role("button", name=re.compile(r"Join now|Join meeting", re.I)).first
            await join_btn.click(timeout=15000, force=True)
            await asyncio.sleep(2)
        except Exception:
            pass

        # 1. Click "Continue on this browser" or "Use web app instead"
        logger.info("[Static] Waiting for 'Continue on this browser' …")
        try:
            await page.get_by_test_id("joinOnWeb").click(timeout=60000, force=True)
        except Exception:
            try:
                await page.get_by_text(re.compile(r"Continue on this browser|Use web app instead", re.I)).first.click(timeout=60000, force=True)
            except Exception:
                pass # might already be past this screen

        # 2. Handle 'Continue without audio or video' BEFORE name input
        logger.info("[Static] Checking for missing permissions prompt …")
        try:
            no_av_btn = page.get_by_role("button", name=re.compile(r"Continue without audio or video", re.I)).first
            await no_av_btn.click(timeout=20000, force=True)
            await asyncio.sleep(1)
        except Exception:
            pass

        # 3. Enter Name
        logger.info("[Static] Waiting for name input …")
        try:
            name_input = page.get_by_placeholder(re.compile(r"name", re.I)).first
            await name_input.wait_for(state="visible", timeout=60000)
            await name_input.fill(self.display_name)
        except Exception:
            logger.info("[Static] Could not find name input placeholder, proceeding anyway.")

        # 4. Click Join Now
        logger.info("[Static] Clicking Join now …")
        try:
            join_now_btn = page.get_by_role("button", name=re.compile(r"Join now", re.I)).first
            await join_now_btn.click(timeout=60000, force=True)
        except Exception:
            logger.warning("[Static] Could not click 'Join now'.")

        # 5. Verify joined
        logger.info("[Static] Waiting for meeting room to load …")
        try:
            proof = page.get_by_role("button", name=re.compile(r"Leave|Hang up|Chat|People|Participants", re.I)).first
            await proof.wait_for(state="visible", timeout=60000)
            
            await page.evaluate(MUTATION_OBSERVER_SCRIPT)
            self._joined = True
            logger.info("✓ Successfully joined the meeting (Static Automation)")
            return
        except Exception:
            raise Exception("Could not verify we entered the meeting room.")

    async def _join_meeting_vision(self, url: str) -> None:
        """Navigate to the meeting URL and use Groq vision to join."""
        page = self._page
        logger.info("Navigating to Teams meeting URL …")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # let the page settle

        # Inject DOM mutation observer
        await page.evaluate(MUTATION_OBSERVER_SCRIPT)

        start = time.monotonic()

        while (time.monotonic() - start) < JOIN_TIMEOUT_SECONDS:
            if self.shutdown_event.is_set():
                logger.info("Shutdown requested during join phase")
                return

            # 1 — screenshot
            screenshot_bytes = await page.screenshot()
            b64 = base64.b64encode(screenshot_bytes).decode()

            # 2 — ask Groq what to do
            action = await self._ask_groq_join(b64)
            if action is None:
                await asyncio.sleep(3)
                continue

            action_type = action.get("action", "").upper()
            desc = action.get("description", "")
            logger.info("Groq action: %s — %s", action_type, desc)

            # 3 — execute
            if action_type == "JOINED":
                self._joined = True
                logger.info("✓ Successfully joined the meeting")
                return

            if action_type == "ENDED":
                self._ended = True
                self.shutdown_event.set()
                logger.info("Meeting has ended (detected during join)")
                return

            if action_type == "CLICK":
                await self._execute_click(desc)
            elif action_type == "TYPE":
                text = action.get("text", self.display_name)
                await page.keyboard.type(text, delay=50)
                logger.info("Typed: %s", text)
            elif action_type == "WAIT":
                logger.info("Waiting (page loading) …")
            elif action_type == "DISMISS":
                await self._execute_dismiss()
            else:
                logger.warning("Unknown action type: %s", action_type)

            await asyncio.sleep(2)

        # Timeout reached
        logger.error("Join timeout after %d seconds", JOIN_TIMEOUT_SECONDS)
        debug_path = self.output_dir / "debug_screenshot.png"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(debug_path))
        logger.error("Saved debug screenshot to %s", debug_path)
        raise TimeoutError(
            f"Could not join meeting within {JOIN_TIMEOUT_SECONDS}s. "
            f"Debug screenshot saved to {debug_path}"
        )

    async def _ask_groq_join(self, b64_screenshot: str) -> dict | None:
        """Send a screenshot to Groq and parse the JSON action response."""
        # Substitute display name into the prompt
        prompt = JOIN_PROMPT.replace("Meeting Recorder", self.display_name)

        for attempt in range(3):
            try:
                response = self.groq.chat.completions.create(
                    model=self.vision_model,
                    max_tokens=300,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{b64_screenshot}",
                                    },
                                },
                                {"type": "text", "text": prompt},
                            ],
                        }
                    ],
                )
                raw = response.choices[0].message.content.strip()
                # Strip markdown code fences
                raw = re.sub(
                    r"^```json\s*|^```\s*|```$", "", raw, flags=re.MULTILINE
                ).strip()
                return json.loads(raw)

            except json.JSONDecodeError:
                logger.warning("Groq returned malformed JSON: %s", raw)
                return None  # caller will wait 3s and retry via the outer loop

            except Exception as exc:
                logger.warning(
                    "Groq API error (attempt %d/3): %s", attempt + 1, exc
                )
                if attempt < 2:
                    await asyncio.sleep(5)
                else:
                    logger.error("Groq API failed after 3 attempts")
                    raise

        return None

    # ── Click / dismiss helpers ────────────────────────────────────────

    async def _execute_click(self, description: str) -> None:
        """Try several Playwright strategies to click the described element."""
        page = self._page
        strategies = [
            lambda: page.get_by_role(
                "button", name=re.compile(description, re.IGNORECASE)
            ).click(timeout=3000, force=True),
            lambda: page.get_by_text(
                re.compile(description, re.IGNORECASE)
            ).first.click(timeout=3000, force=True),
            lambda: page.locator(f"text={description}").first.click(
                timeout=3000, force=True
            ),
        ]
        for i, strategy in enumerate(strategies):
            try:
                await strategy()
                logger.info("Click succeeded (strategy %d)", i + 1)
                return
            except Exception:
                continue

        logger.warning("All click strategies failed for: %s", description)

    async def _execute_dismiss(self) -> None:
        """Try to dismiss a popup — Escape first, then look for Cancel."""
        page = self._page
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        try:
            await page.get_by_role(
                "button", name=re.compile(r"cancel|close|no|stay", re.IGNORECASE)
            ).click(timeout=2000)
        except Exception:
            pass

    # ── Stay-alive loop ────────────────────────────────────────────────

    async def _stay_alive_loop(self) -> None:
        """Periodically check if the meeting is still active.

        Checks the DOM for 'Rejoin' buttons or 'has ended' text to
        determine if the meeting is over, saving vision tokens.
        """
        check_interval = 10
        logger.info("Entering stay-alive loop (checking DOM every %ds)", check_interval)

        while not self.shutdown_event.is_set():
            await asyncio.sleep(check_interval)

            try:
                # Check if the meeting has ended by looking for common exit screens
                ended = await self._page.evaluate('''() => {
                    const text = document.body.innerText || "";
                    if (text.includes("The meeting has ended")) return true;
                    if (text.includes("You've left the meeting")) return true;
                    
                    // Look for Rejoin button
                    const buttons = Array.from(document.querySelectorAll("button"));
                    const hasRejoin = buttons.some(b => (b.innerText || "").toLowerCase().includes("rejoin"));
                    if (hasRejoin) return true;
                    
                    return false;
                }''')
                
                if ended:
                    logger.info("Meeting ended (detected via DOM text)")
                    self._ended = True
                    self.shutdown_event.set()
                    break
            except Exception:
                logger.debug("Stay-alive DOM check failed", exc_info=True)
                pass

    async def _handle_unexpected_popup(self) -> None:
        """Run one iteration of the join click-loop to dismiss a popup."""
        try:
            screenshot_bytes = await self._page.screenshot()
            b64 = base64.b64encode(screenshot_bytes).decode()
            action = await self._ask_groq_join(b64)
            if action:
                action_type = action.get("action", "").upper()
                if action_type == "ENDED":
                    self._ended = True
                    self.shutdown_event.set()
                elif action_type == "CLICK":
                    await self._execute_click(action.get("description", ""))
                elif action_type == "DISMISS":
                    await self._execute_dismiss()
        except Exception:
            logger.warning("Popup handling failed", exc_info=True)
