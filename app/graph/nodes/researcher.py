from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from app.config import settings
from app.graph.state import MeetingState
from app.models.enums import ChunkClassification
from app.models.schemas import ResearchBrief
from app.services.rag import get_rag_service
from app.services.tavily_client import get_tavily_search

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (
    Path(__file__).resolve().parent.parent.parent.parent / "prompts" / "researcher.txt"
).read_text()

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    api_key=settings.anthropic_api_key,
    max_tokens=1024,
    temperature=0,
)


async def _extract_question(chunk_text: str) -> str:
    """Use the LLM to extract a concise research question from the chunk."""
    response = await llm.ainvoke([
        HumanMessage(
            content=(
                "Extract a single, concise research question from the following "
                "meeting transcript excerpt. Reply with ONLY the question, nothing else.\n\n"
                f"Excerpt: {chunk_text}"
            )
        )
    ])
    return response.content.strip()


async def researcher_node(state: MeetingState) -> dict:
    """Research agent: retrieves context from RAG and/or the web, then synthesizes."""
    classified = state.get("classified", [])
    research_chunks = [
        c for c in classified
        if c.classification == ChunkClassification.RESEARCH_TRIGGER.value
    ]

    if not research_chunks:
        return {"research": []}

    meeting_id = state.get("meeting_id", "")
    briefs: list[ResearchBrief] = []

    for item in research_chunks:
        try:
            question = await _extract_question(item.chunk.text)

            # Stage 1: RAG retrieval
            rag_results = get_rag_service().query(
                question=question,
                meeting_id=meeting_id,
                top_k=5,
            )

            from_rag = True
            good_results = [r for r in rag_results if r["distance"] <= 0.7]

            # Stage 2: fall back to Tavily if RAG insufficient
            if len(good_results) < 2:
                from_rag = False
                web_results = await get_tavily_search().search(query=question, max_results=5)
                sources_text = "\n\n".join(
                    f"[{r['title']}]({r['url']})\n{r['content']}"
                    for r in web_results
                )
            else:
                sources_text = "\n\n".join(
                    f"[RAG result] {r['text']}" for r in good_results
                )

            # Stage 3: synthesize with Claude
            prompt = PROMPT_TEMPLATE.format(
                question=question,
                sources=sources_text or "(no sources found)",
            )
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = response.content.strip()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Failed to parse researcher output: %s", raw)
                data = {"summary": raw, "sources": []}

            brief = ResearchBrief(
                query=question,
                summary=data.get("summary", raw),
                sources=data.get("sources", []),
                from_rag=from_rag,
            )
            briefs.append(brief)

        except Exception as e:
            logger.exception("Research failed for chunk: %s", item.chunk.text[:80])
            briefs.append(
                ResearchBrief(
                    query=item.chunk.text[:200],
                    summary=f"Research failed: {e}",
                    sources=[],
                    from_rag=False,
                )
            )

    return {"research": briefs}
