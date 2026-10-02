"""Unit tests for booking helpers: reference format and expire cutoff math.

Reference format matches CC-{ABBREV}-{YYYYMMDD}-{HEX} and is unique across many
calls; the expire cutoff equals now - PENDING_HOLD_MINUTES.

Requirements: 5.6, 6.8
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.core.config import settings
from app.services.booking import expire_cutoff, generate_reference

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
    refs = {generate_reference(loc, on) for _ in range(500)}
    # The 4-hex suffix gives 65536 values; 500 draws should be distinct in practice.
    assert len(refs) == 500


def test_expire_cutoff_uses_pending_hold_minutes() -> None:
    now = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    cutoff = expire_cutoff(now)
    assert cutoff == now - timedelta(minutes=settings.PENDING_HOLD_MINUTES)
