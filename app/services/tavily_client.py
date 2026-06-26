from __future__ import annotations

import asyncio
import logging

from tavily import TavilyClient

from app.config import settings

logger = logging.getLogger(__name__)


class TavilySearch:
    """Thin wrapper around the Tavily web-search API."""

    def __init__(self) -> None:
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search the web and return simplified results.

        TavilyClient is synchronous; run it in a thread-pool executor so it
        never blocks the asyncio event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.search(query=query, max_results=max_results),
            )
            return [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                }
                for item in response.get("results", [])
            ]
        except Exception:
            logger.exception("Tavily search failed for query: %s", query)
            return []


_tavily_search: TavilySearch | None = None


def get_tavily_search() -> TavilySearch:
    global _tavily_search
    if _tavily_search is None:
        _tavily_search = TavilySearch()
    return _tavily_search
