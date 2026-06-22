from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TeamsBot:
    """Stub for Microsoft Teams bot integration.

    Full implementation requires Azure Bot Service registration.
    This stub provides the interface that other components depend on.
    """

    def __init__(self) -> None:
        self.client_id = settings.ms_graph_client_id
        self.client_secret = settings.ms_graph_client_secret
        self.tenant_id = settings.ms_graph_tenant_id
        self._access_token: str | None = None

    async def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    async def join_meeting(self, meeting_url: str) -> dict:
        """Join a Teams meeting. Requires Azure Bot Service with media permissions."""
        logger.info("TeamsBot.join_meeting called (stub) for: %s", meeting_url)
        return {"status": "stub", "meeting_url": meeting_url}

    async def send_adaptive_card(self, user_id: str, card: dict) -> bool:
        """Send an adaptive card to a user via Teams."""
        try:
            token = await self._get_access_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://graph.microsoft.com/v1.0/users/{user_id}/teamwork/sendActivityNotification",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "topic": {
                            "source": "text",
                            "value": "Meeting System Approval",
                        },
                        "activityType": "approvalRequired",
                        "previewText": {"content": "Action required: Meeting follow-up approval"},
                        "templateParameters": [
                            {"name": "card", "value": str(card)},
                        ],
                    },
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send adaptive card to %s", user_id)
            return False

    async def leave_meeting(self) -> None:
        logger.info("TeamsBot.leave_meeting called (stub)")


teams_bot = TeamsBot()
