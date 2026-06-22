"""Jira REST API client for creating and querying issues."""

from __future__ import annotations

import base64
import logging

import httpx

from app.config import settings
from app.models.schemas import ExtractedTask

logger = logging.getLogger(__name__)

PRIORITY_MAP: dict[str, str] = {
    "high": "1",
    "medium": "3",
    "low": "4",
}


class JiraClient:
    """Async client for the Jira Cloud REST API v3."""

    def __init__(self) -> None:
        self.base_url = settings.jira_base_url.rstrip("/")
        self.project_key = settings.jira_project_key
        self._email = settings.jira_email
        self._api_token = settings.jira_api_token

        # Basic auth: base64(email:api_token)
        credentials = base64.b64encode(
            f"{self._email}:{self._api_token}".encode()
        ).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------ #
    #  Public methods
    # ------------------------------------------------------------------ #

    async def create_issue(self, task: ExtractedTask) -> str:
        """Create a Jira issue from an ExtractedTask.

        Returns the browse URL for the created ticket
        (e.g. https://myorg.atlassian.net/browse/MEET-42).
        """
        priority_id = PRIORITY_MAP.get(task.priority, "3")

        payload: dict = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": task.task_description,
                "issuetype": {"name": "Task"},
                "priority": {"id": priority_id},
                "description": {
                    "version": 1,
                    "type": "doc",
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": task.task_description,
                                }
                            ],
                        }
                    ],
                },
            }
        }

        # Assignee — use displayName search if available
        if task.assignee and not task.is_ambiguous:
            payload["fields"]["assignee"] = {"displayName": task.assignee}

        # Deadline
        if task.deadline:
            payload["fields"]["duedate"] = task.deadline

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/rest/api/3/issue",
                headers=self._headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            ticket_key = data["key"]
            browse_url = f"{self.base_url}/browse/{ticket_key}"
            logger.info("Created Jira issue %s: %s", ticket_key, task.task_description)
            return browse_url

    async def get_issue(self, ticket_key: str) -> dict:
        """Fetch a single Jira issue by its key (e.g. MEET-42)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rest/api/3/issue/{ticket_key}",
                headers=self._headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

    async def list_project_issues(self) -> list[dict]:
        """List issues for the configured project using JQL."""
        jql = f"project = {self.project_key} ORDER BY created DESC"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/rest/api/3/search",
                headers=self._headers,
                params={"jql": jql, "maxResults": 50},
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("issues", [])
