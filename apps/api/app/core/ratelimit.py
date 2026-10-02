"""Shared slowapi rate limiter.

Keys on the real client IP. Because uvicorn runs behind Caddy with
--proxy-headers / --forwarded-allow-ips, request.client.host reflects the real
client IP from the trusted X-Forwarded-For header.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
