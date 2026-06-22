from __future__ import annotations

import logging

from tavily import TavilyClient

from app.config import settings

logger = logging.getLogger(__name__)


class TavilySearch:
    """Thin wrapper around the Tavily web-search API."""

    def __init__(self) -> None:
        self.client = TavilyClient(api_key=settings.tavily_api_key)

    async def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search the web and return simplified results."""
        try:
            response = self.client.search(query=query, max_results=max_results)
            results: list[dict] = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                })
            return results
        except Exception:
            logger.exception("Tavily search failed for query: %s", query)
            return []


_tavily_search: TavilySearch | None = None


def get_tavily_search() -> TavilySearch:
    global _tavily_search
    if _tavily_search is None:
        _tavily_search = TavilySearch()
    return _tavily_search
