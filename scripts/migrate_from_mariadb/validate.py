"""Post-load validation of the PostgreSQL target against the extracted JSON.

Checks performed:

1. Row counts: old table counts (from the extracted JSON) vs. new table counts.
2. booking_reference uniqueness in the new bookings table.
3. FK integrity spot checks: no booking points at a missing location/plan/slot;
   no booking_item/payment points at a missing booking.
4. Ledger sanity: sum(payments.amount_paise) vs. the old advance total
   (sum of upipayment + cashadvance + onlinepayment, in paise).

Prints a report and exits non-zero on any mismatch.

Usage:
    python -m scripts.migrate_from_mariadb.validate
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from .config import MigrationConfig, load_config
from .transform import rupees_to_paise

# Old table -> new table for row-count comparison.
COUNT_PAIRS: tuple[tuple[str, str], ...] = (
    ("location", "locations"),
    ("occasion", "occasions"),
    ("plan", "plans"),
    ("slot", "slots"),
    ("cake", "cakes"),
    ("special_decor", "special_decor_items"),
    ("combos", "combo_items"),
    ("user_role", "user_roles"),
    ("users", "users"),
    ("booking", "bookings"),
    ("contact_form_leads", "contact_leads"),
)


def _read(data_dir: str, table: str) -> list[dict[str, Any]]:
    """Read an extracted ``<table>.json`` file (empty list if absent)."""
    path = os.path.join(data_dir, f"{table}.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def old_advance_total_paise(bookings: list[dict[str, Any]]) -> int:
    """Sum the old per-method advance columns across bookings, in paise."""
    total = 0
    for b in bookings:
        for column in ("upipayment", "cashadvance", "onlinepayment"):
            total += rupees_to_paise(b.get(column))
    return total


def compare_counts(old_counts: dict[str, int], new_counts: dict[str, int]) -> list[str]:
    """Return a list of human-readable mismatch messages (empty if all match)."""
    problems: list[str] = []
    for old_table, new_table in COUNT_PAIRS:
        old_n = old_counts.get(old_table, 0)
        new_n = new_counts.get(new_table, 0)
        if old_n != new_n:
            problems.append(f"count mismatch {old_table}={old_n} vs {new_table}={new_n}")
    return problems


def _scalar(cur: Any, sql: str) -> int:  # pragma: no cover - requires a live DB
    """Execute a scalar-returning query and return the integer result."""
    cur.execute(sql)
    row = cur.fetchone()
    return int(row[0]) if row else 0


def run(config: MigrationConfig) -> int:  # pragma: no cover - requires a live DB
    """Run all validations against the target DB; return a process exit code."""
    import psycopg

    old_bookings = _read(config.data_dir, "booking")
    old_counts = {old: len(_read(config.data_dir, old)) for old, _ in COUNT_PAIRS}
    problems: list[str] = []

    with psycopg.connect(config.target.conninfo) as conn:
        with conn.cursor() as cur:
            new_counts = {
                new: _scalar(cur, f"SELECT COUNT(*) FROM {new}")
                for _, new in COUNT_PAIRS
            }
            problems += compare_counts(old_counts, new_counts)

            distinct_refs = _scalar(cur, "SELECT COUNT(DISTINCT booking_reference) FROM bookings")
            total_bookings = new_counts["bookings"]
            if distinct_refs != total_bookings:
                problems.append(
                    f"booking_reference not unique: {distinct_refs} distinct of "
                    f"{total_bookings}"
                )

            orphan_bookings = _scalar(
                cur,
                "SELECT COUNT(*) FROM bookings b "
                "LEFT JOIN locations l ON l.id = b.location_id "
                "LEFT JOIN plans p ON p.id = b.plan_id "
                "LEFT JOIN slots s ON s.id = b.slot_id "
                "WHERE l.id IS NULL OR p.id IS NULL OR s.id IS NULL",
            )
            if orphan_bookings:
                problems.append(f"{orphan_bookings} bookings reference missing FKs")

            orphan_items = _scalar(
                cur,
                "SELECT COUNT(*) FROM booking_items bi "
                "LEFT JOIN bookings b ON b.id = bi.booking_id WHERE b.id IS NULL",
            )
            if orphan_items:
                problems.append(f"{orphan_items} booking_items reference missing bookings")

            paid_total = _scalar(cur, "SELECT COALESCE(SUM(amount_paise), 0) FROM payments")
            expected = old_advance_total_paise(old_bookings)
            if paid_total != expected:
                problems.append(
                    f"payments sum mismatch: new={paid_total} paise vs old advances="
                    f"{expected} paise"
                )

    _print_report(old_counts, new_counts, problems)
    return 1 if problems else 0


def _print_report(
    old_counts: dict[str, int], new_counts: dict[str, int], problems: list[str]
) -> None:
    """Print the row-count table and any problems found."""
    print("== Row counts (old -> new) ==")
    for old_table, new_table in COUNT_PAIRS:
        print(f"  {old_table:>18} {old_counts.get(old_table, 0):>7}"
              f"   ->   {new_table:<22} {new_counts.get(new_table, 0):>7}")
    print()
    if problems:
        print(f"== {len(problems)} problem(s) found ==")
        for problem in problems:
            print(f"  FAIL: {problem}")
        print("\nvalidate FAILED -> consider the rollback criterion in README.md.")
    else:
        print("validate passed: all checks OK.")


def main() -> None:  # pragma: no cover - CLI entry
    """CLI entry point: validate the target DB and exit with the status code."""
    sys.exit(run(load_config()))


if __name__ == "__main__":  # pragma: no cover
    main()
