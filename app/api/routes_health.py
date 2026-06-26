from __future__ import annotations

from fastapi import APIRouter

from app.services.redis_queue import get_redis

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    checks = {"status": "ok", "redis": False, "chromadb": False}

    try:
        r = await get_redis()
        await r.ping()
        checks["redis"] = True
    except Exception:
        pass

    try:
        import chromadb
        from app.config import settings

        client = chromadb.PersistentClient(path=settings.chromadb_path)
        client.heartbeat()
        checks["chromadb"] = True
    except Exception:
        pass

    if not checks["redis"] or not checks["chromadb"]:
        checks["status"] = "degraded"

    return checks
