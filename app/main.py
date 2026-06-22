from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes_approval import router as approval_router
from app.api.routes_health import router as health_router
from app.api.routes_meeting import router as meeting_router
from app.api.routes_rag import router as rag_router
from app.services.redis_queue import close_redis, ensure_stream_group, CONSUMER_GROUP, STREAM_CHUNKS, STREAM_HITL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Meeting System...")
    try:
        await ensure_stream_group(STREAM_CHUNKS, CONSUMER_GROUP)
        await ensure_stream_group(STREAM_HITL, CONSUMER_GROUP)
        logger.info("Redis streams initialized")
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

app.include_router(health_router)
app.include_router(meeting_router)
app.include_router(rag_router)
app.include_router(approval_router)


@app.get("/")
async def root():
    return {
        "name": "AI Meeting System",
        "version": "1.0.0",
        "docs": "/docs",
    }
