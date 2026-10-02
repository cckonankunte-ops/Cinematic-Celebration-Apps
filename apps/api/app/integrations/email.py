"""Transactional email over SMTP.

Configuration comes from the environment (SMTP_* settings). When SMTP_HOST is
empty (local/test), the sender is a no-op so flows do not fail without a mail
server. Never log PII beyond what is necessary; never log credentials.
"""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("app.integrations.email")


def send_email(
    to: str, subject: str, html: str, bcc: str | None = None
) -> None:
    """Send an HTML email via SMTP.

    No-op (log and return) when SMTP_HOST is not configured so tests and local
    development do not require a mail server.
    """
    if not settings.SMTP_HOST:
        log.info("email_skipped_no_smtp", subject=subject)
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    if bcc:
        message["Bcc"] = bcc
    message.set_content("This email requires an HTML-capable client.")
    message.add_alternative(html, subtype="html")

    try:  # pragma: no cover - real SMTP send is not exercised in tests
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(message)
        log.info("email_sent", subject=subject)
    except Exception:  # pragma: no cover - log and swallow so callers never fail
        log.error("email_send_failed", subject=subject)
