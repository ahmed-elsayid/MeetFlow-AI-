import sys
import threading
from datetime import datetime
from typing import TypedDict

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END

from bot          import start_bot
from audio        import record_audio
from transcribe   import transcribe
from analyze      import analyze
from notion_tool  import save_to_notion

class MeetingState(TypedDict):
    meeting_url : str
    audio_path  : str
    transcript  : str
    analysis    : dict
    notion_url  : str

def join_and_record(state: MeetingState) -> dict:
    """
    Opens the meeting in a browser (Playwright) and records system audio
    (PyAudioWPatch WASAPI loopback) simultaneously.
    Both run as background threads; main thread waits for Enter to stop.
    """
    url        = state["meeting_url"]
    audio_path = f"meeting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    stop_event = threading.Event()

    audio_thread = threading.Thread(
        target=record_audio,
        args=(stop_event, audio_path),
        daemon=True,
    )
    audio_thread.start()

    bot_thread = threading.Thread(
        target=start_bot,
        args=(url, stop_event),
        daemon=True,
    )
    bot_thread.start()

    print("\n[INFO] To stop recording, create a file named 'stop.txt' in the project directory...")
    import time
    import os
    while not os.path.exists("stop.txt"):
        time.sleep(1)
    
    os.remove("stop.txt")
    print("\n[INFO] Stop signal received!")

    stop_event.set()
    audio_thread.join(timeout=10)
    bot_thread.join(timeout=10)

    return {"audio_path": audio_path}


def transcribe_node(state: MeetingState) -> dict:
    """Transcribe the recorded WAV with Faster-Whisper (local, no API cost)."""
    return {"transcript": transcribe(state["audio_path"])}


def analyze_node(state: MeetingState) -> dict:
    """Extract summary, decisions, and action items with Groq / Llama 3.3 70B."""
    return {"analysis": analyze(state["transcript"])}


def save_to_notion_node(state: MeetingState) -> dict:
    """Create a structured Notion page via the Notion MCP server."""
    print("[MCP] Saving to Notion via MCP...")
    url = save_to_notion(state["analysis"], state["transcript"])
    if url:
        print(f"[MCP] Notion page: {url}")
    else:
        print("[MCP] Meeting notes saved to Notion.")
    return {"notion_url": url or ""}

builder = StateGraph(MeetingState)

builder.add_node("join_and_record", join_and_record)
builder.add_node("transcribe",      transcribe_node)
builder.add_node("analyze",         analyze_node)
builder.add_node("save_to_notion",  save_to_notion_node)

builder.add_edge(START,              "join_and_record")
builder.add_edge("join_and_record",  "transcribe")
builder.add_edge("transcribe",       "analyze")
builder.add_edge("analyze",          "save_to_notion")
builder.add_edge("save_to_notion",   END)

graph = builder.compile()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:   python main.py <meeting_url>")
        print("Example: python main.py https://meet.google.com/xxx-yyyy-zzz")
        sys.exit(1)

    print("\n[*] Agentic AI Meeting Assistant")
    print("=" * 45)

    result = graph.invoke({"meeting_url": sys.argv[1]})

    print("\n" + "=" * 45)
    print("[DONE] Check your Notion workspace for the meeting notes.")
