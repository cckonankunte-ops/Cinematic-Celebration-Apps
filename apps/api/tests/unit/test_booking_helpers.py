"""Unit tests for booking helpers: reference format and expire cutoff math.

Reference format matches CC-{ABBREV}-{YYYYMMDD}-{HEX} and is unique across many
calls; the expire cutoff equals now - PENDING_HOLD_MINUTES.

Also guards the IntegrityError classifier that maps a reused
``uq_bookings_active_slot`` violation to a slot conflict (-> 409). The 0002
migration reuses this index name, so this detection must keep firing.

Requirements: 3.4, 5.6, 6.8
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.services.booking import (
    _classify_integrity_error,
    expire_cutoff,
    generate_reference,
)

_REFERENCE_RE = re.compile(r"^CC-[A-Z0-9]{1,3}-\d{8}-[0-9A-F]{4}$")


def _location(slug: str = "hulimavu", name: str = "Hulimavu") -> SimpleNamespace:
    return SimpleNamespace(slug=slug, name=name)


def test_reference_matches_format() -> None:
    ref = generate_reference(_location(), datetime(2025, 12, 25).date())
    assert _REFERENCE_RE.match(ref), ref
    assert ref.startswith("CC-HUL-20251225-")


def test_reference_falls_back_to_loc_when_no_alnum() -> None:
    ref = generate_reference(_location(slug="", name="---"), datetime(2025, 1, 1).date())
    assert ref.startswith("CC-LOC-20250101-")


def test_references_are_unique_over_many_calls() -> None:
    loc = _location()
    on = datetime(2025, 6, 1).date()
    count = 500
    refs = {generate_reference(loc, on) for _ in range(count)}
    # The 4-hex suffix gives 65536 values, so by the birthday paradox a few
    # collisions in 500 draws are expected (asserting strict 500/500 was flaky).
    # The service's reference-collision retry handles real duplicates at insert
    # time; here we only need to confirm the suffix is high-entropy, so allow a
    # small tolerance while still catching a broken (constant/low-entropy) suffix.
    assert len(refs) >= count - 5
    # Every reference still matches the documented format.
    assert all(_REFERENCE_RE.match(r) for r in refs)


def test_expire_cutoff_uses_pending_hold_minutes() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    cutoff = expire_cutoff(now)
    assert cutoff == now - timedelta(minutes=settings.PENDING_HOLD_MINUTES)


def _integrity_error(message: str) -> IntegrityError:
    """Build an IntegrityError whose ``orig`` stringifies to ``message``.

    The classifier reads ``str(getattr(exc, "orig", exc))``, so the ``orig``
    message substring is all that matters here (no DB needed).
    """
    return IntegrityError(statement="INSERT ...", params=None, orig=Exception(message))


def test_classify_integrity_error_detects_active_slot_conflict() -> None:
    # The 0002 migration reuses the name "uq_bookings_active_slot"; a violation
    # on that index must still classify as a slot conflict (-> 409).
    exc = _integrity_error(
        'duplicate key value violates unique constraint "uq_bookings_active_slot"'
    )
    check = _classify_integrity_error(exc)
    assert check.is_slot_conflict is True
    assert check.is_reference_conflict is False


def test_classify_integrity_error_detects_reference_conflict() -> None:
    exc = _integrity_error(
        'duplicate key value violates unique constraint "uq_bookings_booking_reference"'
    )
    check = _classify_integrity_error(exc)
    assert check.is_reference_conflict is True
    assert check.is_slot_conflict is False
