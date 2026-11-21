"""CLI job: close stale open leads as lost / no_response (lead-crm R14).

Run once a day by cron (03:00 IST):

    python -m app.jobs.auto_close_leads

``LEAD_AUTO_CLOSE_DAYS`` is read when the process starts, i.e. on every run, so
a changed value applies from the next run. With the default ``0`` it closes
nothing and exits normally. Idempotent; opens its own session; logs the count
only (no lead data).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.leads import close_stale_leads

log = get_logger("app.jobs.auto_close_leads")


def main() -> int:
    """Close stale leads and return the number closed."""
    db = SessionLocal()
    try:
        closed = close_stale_leads(
            db, now=datetime.now(UTC), days=settings.LEAD_AUTO_CLOSE_DAYS
        )
        log.info("auto_close_leads_completed", closed=closed)
        return closed
    finally:
        db.close()


if __name__ == "__main__":
    main()
