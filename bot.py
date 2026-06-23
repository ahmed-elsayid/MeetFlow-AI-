import asyncio
import threading
from playwright.async_api import async_playwright


async def _run(url: str, stop_event: threading.Event):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--use-fake-device-for-media-stream",  
                "--use-fake-ui-for-media-stream",       
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context()
        await context.grant_permissions(
            ["microphone", "camera"], origin="https://meet.google.com"
        )
        page = await context.new_page()

        print(f"[BOT] Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        for text in ["Continue without signing in", "Join as a guest"]:
            try:
                await page.get_by_text(text).click(timeout=5000)
                await asyncio.sleep(1)
                print(f"[BOT] Clicked: '{text}'")
                break
            except Exception:
                pass

        try:
            name_input = page.get_by_placeholder("Your name")
            await name_input.wait_for(timeout=5000)
            await name_input.fill("Meeting Bot")
            await asyncio.sleep(1)
        except Exception:
            pass

        joined = False
        for text in ["Ask to join", "Join now", "Join"]:
            try:
                btn = page.get_by_role("button", name=text)
                await btn.wait_for(timeout=6000)
                await btn.click()
                print(f"[BOT] Clicked '{text}' -- bot is in the meeting.")
                joined = True
                break
            except Exception:
                pass

        if not joined:
            print("[BOT] Could not find Join button -- browser is open, join manually if needed.")

        while not stop_event.is_set():
            await asyncio.sleep(0.5)

        await browser.close()
        print("[BOT] Browser closed.")


def start_bot(url: str, stop_event: threading.Event):
    """Blocking call -- runs the browser bot until stop_event is set."""
    asyncio.run(_run(url, stop_event))
