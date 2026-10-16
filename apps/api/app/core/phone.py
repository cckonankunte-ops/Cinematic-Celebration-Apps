"""Pure Indian-mobile phone normalization (no IO).

Shared by booking create/edit validation and the coupon customer_key
derivation so there is exactly one normalization implementation.
"""

from __future__ import annotations

import re

_NON_DIGIT = re.compile(r"[\s\-]")


def normalize_indian_mobile(raw: str) -> str | None:
    """Normalize a raw phone string to a canonical 10-digit Indian mobile.

    Rules (R23.1, R23.2):
      - strip spaces and dashes;
      - drop a single leading country/trunk prefix: '+91', '91', or '0';
      - take the last 10 digits;
      - return the 10-digit string iff it is exactly 10 digits and starts
        with 6, 7, 8, or 9; otherwise return None.

    Examples (R23.4): '+91 98765 43210', '098765 43210', and '9876543210'
    all return '9876543210'. '12345' or '1234567890' return None.
    """
    if raw is None:
        return None
    s = _NON_DIGIT.sub("", raw.strip())
    if s.startswith("+91"):
        s = s[3:]
    elif s.startswith("91") and len(s) > 10:
        s = s[2:]
    elif s.startswith("0"):
        s = s.lstrip("0")
    digits = re.sub(r"\D", "", s)
    last10 = digits[-10:]
    if len(last10) == 10 and last10[0] in "6789":
        return last10
    return None
