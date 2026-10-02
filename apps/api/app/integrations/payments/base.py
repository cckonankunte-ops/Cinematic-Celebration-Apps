"""PaymentProvider seam.

Phase 1 ships only a ManualProvider (no gateway). A real gateway (likely
Cashfree) will be added in a later phase behind this Protocol, implemented from
the gateway's current official documentation. Do not implement any gateway here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable


@runtime_checkable
class PaymentProvider(Protocol):
    """Minimal payment-provider interface the booking service depends on."""

    def create_order(self, booking_reference: str, amount_paise: int) -> str:
        """Return human-readable payment instructions for an advance payment."""
        ...

    def get_status(self, booking_reference: str) -> str:
        """Return the provider-side payment status for a booking."""
        ...

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> object:
        """Verify and parse an incoming gateway webhook (no gateway in Phase 1)."""
        ...
