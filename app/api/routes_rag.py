from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.nodes._llm import build_llm
from app.models.schemas import ChatRequest, ChatResponse, RAGQueryRequest, RAGUploadRequest
from app.services.rag import get_rag_service
from app.services.tavily_client import get_tavily_search

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["rag"])

# ChromaDB returns L2 distances for normalised sentence-transformer vectors.
# L2 dist = 2 - 2*cos_sim, so 1.5 ≈ cos_sim 0.25 (loosely relevant).
# Use a generous threshold so we don't accidentally skip real hits.
_RAG_DISTANCE_THRESHOLD = 1.5


@router.post("/query")
async def rag_query(req: RAGQueryRequest):
    try:
        rag = get_rag_service()
        results = await rag.query(
            question=req.question,
            meeting_id=req.meeting_id,
            speaker=req.speaker,
            minute=req.minute,
        )
        return {"results": results, "count": len(results)}
    except Exception:
        logger.exception("RAG query failed")
        raise HTTPException(500, "RAG query failed")


@router.post("/chat", response_model=ChatResponse)
async def rag_chat(req: ChatRequest):
    """ChatGPT-style Q&A: searches RAG first, falls back to Tavily web search."""
    try:
        rag = get_rag_service()

        # rag.query() never raises — returns [] when collection is empty or model fails
        chunks = await rag.query(question=req.question, meeting_id=req.meeting_id, top_k=4)

        use_rag = bool(chunks) and chunks[0]["distance"] < _RAG_DISTANCE_THRESHOLD
        source = "rag"
        context_parts: list[str] = []

        if use_rag:
            for c in chunks:
                meta = c["metadata"]
                speaker = meta.get("speaker") or "Unknown"
                ts = meta.get("timestamp_start") or ""
                prefix = f"[{speaker} at {ts}]" if ts else f"[{speaker}]"
                context_parts.append(f"{prefix}: {c['text']}")
            logger.info(
                "RAG chat: using %d transcript chunk(s) (best dist=%.3f)",
                len(chunks), chunks[0]["distance"],
            )
        else:
            if chunks:
                logger.info(
                    "RAG chat: %d chunk(s) found but distance %.3f > threshold %.1f; "
                    "falling back to web search",
                    len(chunks), chunks[0]["distance"], _RAG_DISTANCE_THRESHOLD,
                )
            else:
                logger.info("RAG chat: no chunks found; falling back to web search")

            try:
                tavily = get_tavily_search()
                web_results = await tavily.search(req.question, max_results=3)
            except Exception:
                logger.exception("Tavily web search failed")
                web_results = []

            if web_results:
                source = "web"
                for r in web_results:
                    context_parts.append(f"[{r['title']}]: {r['content'][:500]}")
            else:
                source = "none"

        system_prompt = (
            "You are MeetFlow AI, a meeting assistant. "
            "Answer questions based on the provided context from the meeting transcript "
            "or web search results. Be concise and helpful. "
            "If the context is insufficient, say so briefly and answer from general knowledge."
        )

        if context_parts:
            context_block = "\n\n".join(context_parts)
            user_content = f"Context:\n{context_block}\n\nQuestion: {req.question}"
        else:
            user_content = req.question

        messages: list = [SystemMessage(content=system_prompt)]
        for h in req.history[-6:]:
            role = h.get("role", "")
            content = h.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=user_content))

        llm = build_llm(temperature=0)
        try:
            response = await llm.ainvoke(messages)
        except Exception:
            logger.exception("LLM call failed in RAG chat")
            raise

        return ChatResponse(
            answer=str(response.content),
            source=source,
            chunks=chunks if use_rag else [],
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("RAG chat failed")
        raise HTTPException(500, "Chat failed")


@router.post("/upload")
async def rag_upload(req: RAGUploadRequest):
    try:
        rag = get_rag_service()
        await rag.upload_document(
            meeting_id=req.meeting_id,
            text=req.text,
            source_name=req.source_name,
        )
        return {"status": "uploaded", "meeting_id": req.meeting_id}
    except Exception:
        logger.exception("RAG upload failed")
        raise HTTPException(500, "RAG upload failed")
