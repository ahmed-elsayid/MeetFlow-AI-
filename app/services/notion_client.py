"""Notion API client for pushing meeting notes and decisions."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.config import settings
from app.models.schemas import NoteSection

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    """Async client for the Notion API."""

    def __init__(self) -> None:
        self.api_key = settings.notion_api_key
        self.database_id = settings.notion_database_id
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Public helpers
    # ------------------------------------------------------------------ #

    async def create_meeting_page(self, meeting_id: str, title: str) -> str:
        """Create a new page in the configured Notion database.

        Returns the page id.
        """
        payload = {
            "parent": {"database_id": self.database_id},
            "properties": {
                "Name": {
                    "title": [{"text": {"content": title or meeting_id}}],
                },
                "Meeting ID": {
                    "rich_text": [{"text": {"content": meeting_id}}],
                },
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{NOTION_API_BASE}/pages",
                headers=self._headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            page_id: str = response.json()["id"]
            logger.info("Created Notion page %s for meeting %s", page_id, meeting_id)
            return page_id

    async def append_notes(
        self, page_id: str, sections: list[NoteSection]
    ) -> None:
        """Append note sections as block children (heading + bullets)."""
        children: list[dict] = []
        for section in sections:
            # Section heading
            children.append(
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": section.topic}}],
                    },
                }
            )
            # Bullet points
            for point in section.points:
                children.append(
                    {
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": point}}],
                        },
                    }
                )

        if not children:
            return

        await self._append_blocks(page_id, children)

    async def append_decisions(
        self, page_id: str, decisions: list[str]
    ) -> None:
        """Append a 'Decisions' heading followed by a bulleted list."""
        if not decisions:
            return

        children: list[dict] = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Decisions"}}],
                },
            },
        ]
        for decision in decisions:
            children.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": decision}}],
                    },
                }
            )

        await self._append_blocks(page_id, children)

    # ------------------------------------------------------------------ #
    #  Internal
    # ------------------------------------------------------------------ #

    async def _append_blocks(self, page_id: str, children: list[dict]) -> None:
        """PATCH block children onto a Notion page."""
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{NOTION_API_BASE}/blocks/{page_id}/children",
                headers=self._headers,
                json={"children": children},
                timeout=30,
            )
            response.raise_for_status()
            logger.info("Appended %d blocks to Notion page %s", len(children), page_id)
