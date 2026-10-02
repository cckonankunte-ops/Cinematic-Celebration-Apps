"""Payments integration package.

Phase 1 ships only a ManualProvider (no payment gateway). A real gateway (likely
Cashfree) will be added in a later phase behind the PaymentProvider Protocol,
implemented from the gateway's current official documentation. Nothing in this
package talks to an external gateway in Phase 1.
"""

from __future__ import annotations

from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.manual import ManualProvider


def get_payment_provider() -> PaymentProvider:
    """Return the active payment provider (ManualProvider in Phase 1)."""
    return ManualProvider()


__all__ = ["PaymentProvider", "ManualProvider", "get_payment_provider"]
