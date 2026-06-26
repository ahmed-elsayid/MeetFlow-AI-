from __future__ import annotations

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.models.schemas import EmailDraft

logger = logging.getLogger(__name__)


class EmailClient:
    """Send emails via SMTP."""

    async def send(self, draft: EmailDraft) -> bool:
        """Send an email draft via SMTP. Returns True on success."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._send_via_smtp, draft)

    def _send_via_smtp(self, draft: EmailDraft) -> bool:
        """Blocking SMTP send — always called via run_in_executor."""
        if not settings.smtp_user or not settings.smtp_password:
            logger.error("SMTP credentials not configured (SMTP_USER / SMTP_PASSWORD missing)")
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
                server.sendmail(settings.smtp_user, draft.recipients, msg.as_string())

            logger.info("Email sent via SMTP: %s", draft.subject)
            return True

        except Exception:
            logger.exception("SMTP email send failed")
            return False


email_client = EmailClient()
