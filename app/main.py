from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_approval import router as approval_router
from app.api.routes_bot import router as bot_router
from app.api.routes_health import router as health_router
from app.api.routes_hitl import router as hitl_router
from app.api.routes_meeting import router as meeting_router
from app.api.routes_rag import router as rag_router
from app.persistence.database import init_db
from app.services.redis_queue import (
    CONSUMER_GROUP,
    STREAM_CHUNKS,
    STREAM_HITL,
    close_redis,
    ensure_stream_group,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Meeting System...")

    # SQLite persistence — fast, no external dependency
    try:
        init_db()
        logger.info("SQLite persistence initialised")
    except Exception:
        logger.warning("SQLite init failed — running without durable HITL persistence")

    # Redis streams — optional (system degrades gracefully without it)
    try:
        await ensure_stream_group(STREAM_CHUNKS, CONSUMER_GROUP)
        await ensure_stream_group(STREAM_HITL, CONSUMER_GROUP)
        logger.info("Redis streams initialised")
    except Exception:
        logger.warning("Redis not available — running without queue support")

    yield

    await close_redis()
    logger.info("AI Meeting System shut down")


app = FastAPI(
    title="AI Meeting System",
    description="AI-powered meeting assistant for Microsoft Teams",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(meeting_router)
app.include_router(rag_router)
app.include_router(approval_router)
app.include_router(hitl_router)
app.include_router(bot_router)


@app.get("/")
async def root():
    return {
        "name": "AI Meeting System",
        "version": "1.0.0",
        "docs": "/docs",
    }
