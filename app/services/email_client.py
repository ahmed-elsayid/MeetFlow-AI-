from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from app.config import settings
from app.models.schemas import EmailDraft

logger = logging.getLogger(__name__)


class EmailClient:
    """Send emails via Microsoft Graph API or SMTP fallback."""

    async def send(self, draft: EmailDraft) -> bool:
        """Send an email draft. Returns True on success, False on failure."""
        if settings.ms_graph_client_id:
            return await self._send_via_graph(draft)
        return self._send_via_smtp(draft)

    async def _send_via_graph(self, draft: EmailDraft) -> bool:
        """Send using Microsoft Graph Mail API with client credentials."""
        try:
            token = await self._get_graph_token()

            to_recipients = [
                {"emailAddress": {"address": r}} for r in draft.recipients
            ]

            payload = {
                "message": {
                    "subject": draft.subject,
                    "body": {
                        "contentType": "HTML",
                        "content": draft.body_html,
                    },
                    "toRecipients": to_recipients,
                },
                "saveToSentItems": "true",
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://graph.microsoft.com/v1.0/me/sendMail",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30,
                )
                resp.raise_for_status()

            logger.info("Email sent via Graph API: %s", draft.subject)
            return True

        except Exception:
            logger.exception("Graph API email send failed, falling back to SMTP")
            return self._send_via_smtp(draft)

    async def _get_graph_token(self) -> str:
        """Obtain an access token using client credentials grant."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{settings.ms_graph_tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": settings.ms_graph_client_id,
                    "client_secret": settings.ms_graph_client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

    def _send_via_smtp(self, draft: EmailDraft) -> bool:
        """Fallback: send email via SMTP."""
        if not settings.smtp_user or not settings.smtp_password:
            logger.error("SMTP credentials not configured; cannot send email")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = draft.subject
            msg["From"] = settings.smtp_user
            msg["To"] = ", ".join(draft.recipients)

            msg.attach(MIMEText(draft.body_html, "html"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(
                    settings.smtp_user,
                    draft.recipients,
                    msg.as_string(),
                )

            logger.info("Email sent via SMTP: %s", draft.subject)
            return True

        except Exception:
            logger.exception("SMTP email send failed")
            return False


email_client = EmailClient()
