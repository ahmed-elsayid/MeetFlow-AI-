from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import RAGQueryRequest, RAGUploadRequest
from app.services.rag import get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query")
async def rag_query(req: RAGQueryRequest):
    try:
        rag = get_rag_service()
        results = rag.query(
            question=req.question,
            meeting_id=req.meeting_id,
            speaker=req.speaker,
            minute=req.minute,
        )
        return {"results": results, "count": len(results)}
    except Exception:
        logger.exception("RAG query failed")
        raise HTTPException(500, "RAG query failed")


@router.post("/upload")
async def rag_upload(req: RAGUploadRequest):
    try:
        rag = get_rag_service()
        rag.upload_document(
            meeting_id=req.meeting_id,
            text=req.text,
            source_name=req.source_name,
        )
        return {"status": "uploaded", "meeting_id": req.meeting_id}
    except Exception:
        logger.exception("RAG upload failed")
        raise HTTPException(500, "RAG upload failed")
