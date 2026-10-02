"""Pre-migration checks against the source MariaDB. Must pass before loading.

Two checks, matching the design's "Pre-migration checks":

1. Duplicate active slots: more than one pending/accepted booking per
   (locationid, slotid, date). The new ``uq_bookings_active_slot`` partial
   unique index rejects these, so they MUST be resolved manually before load.
   The process exits non-zero when any are found.

2. Legacy cakeid = 1 investigation: prints the cake row with id = 1 and the
   count of bookings referencing cakeid = 1, so a human can confirm whether 1
   means "no cake" (the assumed sentinel) rather than a real cake.

Usage:
    python -m scripts.migrate_from_mariadb.precheck
"""

from __future__ import annotations

import sys
from typing import Any

from .config import CAKEID_NO_CAKE_SENTINEL, MigrationConfig, load_config

# Old statusids that hold a slot (pending, accepted).
ACTIVE_STATUS_IDS: tuple[int, ...] = (1, 2)

_DUP_SQL = """
    SELECT locationid, slotid, `date`, COUNT(*) AS n,
           GROUP_CONCAT(id ORDER BY id) AS booking_ids
    FROM booking
    WHERE statusid IN (%s, %s)
    GROUP BY locationid, slotid, `date`
    HAVING COUNT(*) > 1
    ORDER BY n DESC
"""


def _connect(config: MigrationConfig):  # pragma: no cover - requires a live DB
    """Open a PyMySQL DictCursor connection to the source MariaDB."""
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=config.source.host,
        port=config.source.port,
        user=config.source.user,
        password=config.source.password,
        database=config.source.database,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def find_duplicate_active_slots(cursor: Any) -> list[dict[str, Any]]:
    """Return groups of >1 active booking per (locationid, slotid, date)."""
    cursor.execute(_DUP_SQL, ACTIVE_STATUS_IDS)
    return list(cursor.fetchall())


def investigate_cakeid_one(cursor: Any) -> dict[str, Any]:
    """Return the cake row with id=1 and the count of bookings using cakeid=1."""
    cursor.execute("SELECT * FROM cake WHERE id = %s", (CAKEID_NO_CAKE_SENTINEL,))
    cake_row = cursor.fetchone()
    cursor.execute(
        "SELECT COUNT(*) AS n FROM booking WHERE cakeid = %s",
        (CAKEID_NO_CAKE_SENTINEL,),
    )
    count_row = cursor.fetchone() or {"n": 0}
    return {"cake_row": cake_row, "booking_count": int(count_row["n"])}


def _report_duplicates(duplicates: list[dict[str, Any]]) -> None:
    """Print the duplicate-active-slot report."""
    print("== Check 1: duplicate active (pending/accepted) slots ==")
    if not duplicates:
        print("  OK: no duplicate active slots found.\n")
        return
    print(f"  FAIL: {len(duplicates)} conflicting (location, slot, date) groups:")
    for dup in duplicates:
        print(
            f"    location={dup['locationid']} slot={dup['slotid']} "
            f"date={dup['date']} count={dup['n']} booking_ids={dup['booking_ids']}"
        )
    print("  -> Resolve these manually (cancel/reject extras) before loading.\n")


def _report_cakeid(info: dict[str, Any]) -> None:
    """Print the cakeid=1 investigation report."""
    print("== Check 2: legacy cakeid = 1 investigation ==")
    print(f"  cake row id=1: {info['cake_row']}")
    print(f"  bookings referencing cakeid=1: {info['booking_count']}")
    print(
        "  -> If id=1 is a placeholder/'no cake', the sentinel assumption holds "
        "and no cake booking_item is created for those bookings.\n"
    )


def run(config: MigrationConfig) -> int:  # pragma: no cover - requires a live DB
    """Run both checks; return a process exit code (0 ok, 1 duplicates found)."""
    connection = _connect(config)
    try:
        with connection.cursor() as cursor:
            duplicates = find_duplicate_active_slots(cursor)
            cakeid_info = investigate_cakeid_one(cursor)
    finally:
        connection.close()

    _report_duplicates(duplicates)
    _report_cakeid(cakeid_info)

    if duplicates:
        print("precheck FAILED: resolve duplicate active slots before migrating.")
        return 1
    print("precheck passed. Review the cakeid=1 report above before loading.")
    return 0


def main() -> None:  # pragma: no cover - CLI entry
    """CLI entry point: run prechecks and exit with the resulting status code."""
    config = load_config()
    sys.exit(run(config))


if __name__ == "__main__":  # pragma: no cover
    main()
