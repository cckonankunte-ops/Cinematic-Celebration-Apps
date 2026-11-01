"""Tolerant parser: legacy slot description -> (start_time, duration_minutes).

Legacy descriptions look like "9 AM - 12 PM", "6:30 PM - 7:30 PM", "10AM-1AM".
We parse a start and end 12-hour clock time separated by a dash, compute the
duration (wrapping past midnight), and return ``ParsedSlot``. Anything we cannot
read with confidence returns ``None`` — the retrofit reports it for a human to
map and NEVER guesses a time (spec Requirement 8.3).

Pure and DB-free so it is unit-testable and reusable by the backfill script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time

# One clock time: hour, optional :minutes, am/pm (case/space/dot tolerant).
_TIME = re.compile(
    r"""^\s*
        (?P<hour>\d{1,2})
        (?:[:.](?P<minute>\d{2}))?
        \s*
        (?P<ampm>[ap]\.?\s*m\.?)
        \s*$""",
    re.IGNORECASE | re.VERBOSE,
)

# Dash separators seen in the data: -, –, —, or the word "to".
_SEP = re.compile(r"\s*(?:-|\u2013|\u2014|to)\s*", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSlot:
    start_time: time
    duration_minutes: int


def _parse_clock(token: str) -> time | None:
    """Parse one 12-hour clock token into a ``time`` (minute defaults to 0)."""
    m = _TIME.match(token)
    if m is None:
        return None
    hour = int(m.group("hour"))
    minute = int(m.group("minute") or 0)
    if not (1 <= hour <= 12) or not (0 <= minute <= 59):
        return None
    ampm = m.group("ampm").lower().replace(".", "").replace(" ", "")
    is_pm = ampm.startswith("p")
    # 12 AM -> 00, 12 PM -> 12, otherwise +12 for PM.
    if hour == 12:
        hour24 = 12 if is_pm else 0
    else:
        hour24 = hour + 12 if is_pm else hour
    return time(hour24, minute)


def parse_slot_description(description: str | None) -> ParsedSlot | None:
    """Parse "<start> - <end>" into start + duration; None if unparseable.

    Duration wraps past midnight (e.g. "10 PM - 1 AM" -> 180 min). Equal
    start/end is ambiguous and returns None.
    """
    if not description:
        return None
    parts = _SEP.split(description.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    start = _parse_clock(parts[0])
    end = _parse_clock(parts[1])
    if start is None or end is None:
        return None

    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    duration = end_min - start_min
    if duration < 0:
        duration += 24 * 60  # wrap past midnight
    if duration <= 0 or duration > 24 * 60:
        return None
    return ParsedSlot(start_time=start, duration_minutes=duration)
