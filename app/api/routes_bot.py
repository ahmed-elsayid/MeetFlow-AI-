from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["bot"])

# asyncio.create_subprocess_exec is broken on Windows under SelectorEventLoop
# (uvicorn default).  Use subprocess.Popen + a daemon reader thread instead.

_bot_processes: dict[str, subprocess.Popen] = {}
_bot_logs: dict[str, deque[str]] = {}
_drain_threads: dict[str, threading.Thread] = {}

_BOT_SCRIPT = Path(__file__).resolve().parent.parent.parent / "bot" / "main.py"


class BotStartRequest(BaseModel):
    meeting_id: str
    teams_url: str
    display_name: str = "MeetFlow AI"


def _drain_logs_thread(meeting_id: str, proc: subprocess.Popen) -> None:
    """Daemon thread — reads subprocess stdout into the circular log buffer."""
    log: deque[str] = _bot_logs[meeting_id]
    try:
        for raw in proc.stdout:  # type: ignore[union-attr]
            line = raw.decode("utf-8", errors="replace").rstrip()
            log.append(line)
            logger.debug("[bot:%s] %s", meeting_id, line)
    except Exception:
        pass
    finally:
        proc.wait()
        logger.info(
            "Bot for meeting %s exited (code=%s)", meeting_id, proc.returncode
        )


@router.post("/start")
async def start_bot(req: BotStartRequest):
    """Spawn the Playwright bot for a Teams meeting link."""
    existing = _bot_processes.get(req.meeting_id)
    if existing is not None and existing.poll() is None:
        raise HTTPException(400, detail="Bot is already running for this meeting")

    if not _BOT_SCRIPT.exists():
        raise HTTPException(500, detail=f"Bot script not found: {_BOT_SCRIPT}")

    output_dir = str(
        Path(__file__).resolve().parent.parent.parent / "output" / req.meeting_id
    )
    env = {
        **os.environ,
        "APP_SERVER_URL": os.environ.get("APP_SERVER_URL", "http://localhost:8080"),
        "APP_MEETING_ID": req.meeting_id,
        "BOT_DISPLAY_NAME": req.display_name,
        "OUTPUT_DIR": output_dir,
    }

    try:
        proc = subprocess.Popen(
            [sys.executable, str(_BOT_SCRIPT), "--url", req.teams_url],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:
        logger.exception("Failed to spawn bot for meeting %s", req.meeting_id)
        raise HTTPException(500, detail=f"Failed to start bot: {exc}")

    _bot_processes[req.meeting_id] = proc
    _bot_logs[req.meeting_id] = deque(maxlen=200)

    thread = threading.Thread(
        target=_drain_logs_thread,
        args=(req.meeting_id, proc),
        daemon=True,
        name=f"bot-log-{req.meeting_id}",
    )
    thread.start()
    _drain_threads[req.meeting_id] = thread

    logger.info("Bot started for meeting %s — PID %s", req.meeting_id, proc.pid)
    return {"status": "started", "pid": proc.pid, "meeting_id": req.meeting_id}


@router.get("/status/{meeting_id}")
async def bot_status(meeting_id: str):
    """Return current bot status and recent log tail."""
    proc = _bot_processes.get(meeting_id)
    logs = list(_bot_logs.get(meeting_id, []))

    if proc is None:
        return {"status": "not_started", "pid": None, "exit_code": None, "recent_logs": []}

    exit_code = proc.poll()

    if exit_code is None:
        return {"status": "running", "pid": proc.pid, "exit_code": None, "recent_logs": logs[-60:]}

    return {"status": "stopped", "pid": proc.pid, "exit_code": exit_code, "recent_logs": logs[-60:]}


@router.post("/stop/{meeting_id}")
async def stop_bot(meeting_id: str):
    """Terminate the bot subprocess."""
    proc = _bot_processes.get(meeting_id)
    if proc is None:
        raise HTTPException(404, detail="No bot registered for this meeting")

    exit_code = proc.poll()
    if exit_code is not None:
        return {"status": "already_stopped", "exit_code": exit_code}

    proc.terminate()
    logger.info("Sent SIGTERM to bot PID %s (meeting %s)", proc.pid, meeting_id)
    return {"status": "stopping", "pid": proc.pid}
