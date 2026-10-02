"""Confirmation email service.

send_confirmation is safe to call from FastAPI BackgroundTasks after a request:
it opens its own Session (the request session is closed after the response),
reloads the booking, dedupes on confirmation_sent_at, renders a simple HTML
body, and sends it via integrations.email.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.integrations.email import send_email
from app.models.booking import Booking
from app.models.slot import Slot

log = get_logger("app.services.email")


def _render_confirmation_html(booking: Booking, check_in: str) -> str:
    """Render a simple confirmation email body for a booking."""
    return (
        f"<p>Hi {booking.booking_name},</p>"
        f"<p>Your Cinematic Celebration booking is confirmed.</p>"
        f"<ul>"
        f"<li><strong>Reference:</strong> {booking.booking_reference}</li>"
        f"<li><strong>Date:</strong> {booking.booking_date.isoformat()}</li>"
        f"<li><strong>Check-in:</strong> {check_in}</li>"
        f"<li><strong>People:</strong> {booking.people}</li>"
        f"</ul>"
        f"<p>View your booking status at "
        f"https://cinematiccelebration.in/booking-status?token={booking.public_token}</p>"
        f"<p>See you soon!</p>"
    )


def send_confirmation(booking_id: int) -> None:
    """Send a one-time confirmation email for a booking (dedupe on sent_at)."""
    db = SessionLocal()
    try:
        booking = db.get(Booking, booking_id)
        if booking is None:
            log.info("confirmation_skipped_missing", booking_id=booking_id)
            return
        if booking.confirmation_sent_at is not None:
            log.info("confirmation_skipped_already_sent", booking_id=booking_id)
            return

        slot = db.get(Slot, booking.slot_id)
        check_in = slot.description if slot is not None else ""
        html = _render_confirmation_html(booking, check_in)
        send_email(
            to=booking.email,
            subject="Your Cinematic Celebration booking is confirmed",
            html=html,
            bcc=settings.BUSINESS_EMAIL,
        )
        booking.confirmation_sent_at = datetime.now(UTC)
        db.commit()
        log.info("confirmation_sent", booking_id=booking_id)
    finally:
        db.close()
