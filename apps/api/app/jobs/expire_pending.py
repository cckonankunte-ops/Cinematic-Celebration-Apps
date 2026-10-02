"""CLI job: expire pending bookings older than PENDING_HOLD_MINUTES.

Run every minute by cron or a systemd timer:

    python -m app.jobs.expire_pending

The job is idempotent (a second immediate run is a no-op) and opens its own
database session. It never uses an in-process scheduler.
"""

from __future__ import annotations

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.services.booking import expire_pending_bookings

log = get_logger("app.jobs.expire_pending")


def main() -> int:
    """Expire overdue pending bookings and return the number expired."""
    db = SessionLocal()
    try:
        count = expire_pending_bookings(db)
        log.info("expire_pending_completed", expired=count)
        return count
    finally:
        db.close()


if __name__ == "__main__":
    main()
