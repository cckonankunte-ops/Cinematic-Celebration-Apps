"""today_ist() returns the IST calendar date, not the (UTC) server date."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services import slots


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        # 2026-11-14 20:00 UTC == 2026-11-15 01:30 IST.
        return datetime(2026, 11, 14, 20, 0, tzinfo=UTC).astimezone(tz)


def test_today_ist_is_next_day_after_1830_utc(monkeypatch) -> None:
    monkeypatch.setattr(slots, "datetime", _FrozenDatetime)
    assert slots.today_ist() == date(2026, 11, 15)
