"""Manual payment provider (Phase 1 — no gateway).

A customer booking is a *request*: the ManualProvider returns UPI payment
instructions and holds the slot in `pending` state for PENDING_HOLD_MINUTES.
Staff record the advance in the admin panel and accept/reject the booking.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.core.config import settings


class ManualProvider:
    """Phase 1 provider: no external gateway, UPI instructions only."""

    def create_order(self, booking_reference: str, amount_paise: int) -> str:
        """Return UPI payment instructions for the given advance amount."""
        rupees = amount_paise // 100
        return (
            f"Pay Rs.{rupees} advance via UPI to {settings.MANUAL_UPI_VPA} and share "
            f"the payment reference along with your booking reference "
            f"{booking_reference} with our team on WhatsApp. Your slot is held for "
            f"{settings.PENDING_HOLD_MINUTES} minutes."
        )

    def get_status(self, booking_reference: str) -> str:
        """No gateway in Phase 1; payments are tracked in the ledger."""
        return "manual"

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> object:
        """No gateway webhook exists in Phase 1."""
        raise NotImplementedError("No gateway in Phase 1")
