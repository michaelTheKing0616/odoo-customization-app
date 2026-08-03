"""Dev/console email transport for verification and reset flows (MON-1)."""

from __future__ import annotations

import logging

from app.settings import settings

logger = logging.getLogger(__name__)


def send_email(*, to: str, subject: str, body: str) -> None:
    """Send email via configured transport. Dev default logs only."""
    transport = settings.email_transport.strip().lower()
    if transport in {"console", "log", ""}:
        logger.info(
            "[EMAIL console transport — not delivered]\nTo: %s\nSubject: %s\n%s",
            to,
            subject,
            body,
        )
        return
    if transport == "smtp":
        _send_smtp(to=to, subject=subject, body=body)
        return
    logger.warning("Unknown EMAIL_TRANSPORT=%s — logging email instead", transport)
    logger.info("To: %s Subject: %s\n%s", to, subject, body)


def _send_smtp(*, to: str, subject: str, body: str) -> None:
    import smtplib
    from email.message import EmailMessage

    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST required when EMAIL_TRANSPORT=smtp")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "noreply@localhost"
    msg["To"] = to
    msg.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password or "")
        smtp.send_message(msg)
