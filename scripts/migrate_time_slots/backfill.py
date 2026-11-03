"""One-off retrofit for time-range slots (spec Requirement 8).

Run AFTER migration A (0011) which adds the nullable columns, and BEFORE
migration B which enforces NOT NULL / CHECK / the overlap exclusion constraint.

Steps (idempotent; safe to re-run):
  1. Parse every slot ``description`` -> (start_time, duration_minutes) and write
     the columns. Unparseable descriptions are written to a report file and left
     NULL — never guessed.
  2. Snapshot each booking's start_time/duration_minutes from its slot.
  3. Seed ``plan_pricing``: one row per plan at its predominant existing duration
     (defaults to 120 if unknown) using the plan's current price/advance.
  4. Overlap pre-check: report any active (pending|accepted) bookings whose new
     occupied windows overlap for the same (location, plan, date). These MUST be
     resolved before migration B can enable the exclusion constraint.

Usage (from repo root, with the API venv active):
    export DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/cinematic'
    python -m scripts.migrate_time_slots.backfill [--buffer 30] [--report out.txt]

Connection: uses DATABASE_URL (psycopg scheme stripped of any +driver suffix).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta

import psycopg

# The parser lives in the app package; make it importable when run from repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "apps", "api"))
from app.services.slot_parse import parse_slot_description  # noqa: E402


def _conninfo() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("NEW_DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL (or NEW_DATABASE_URL).")
    # psycopg wants a plain postgresql:// URL, not postgresql+psycopg://.
    return url.replace("postgresql+psycopg://", "postgresql://")


def backfill_slots(cur: psycopg.Cursor, report: list[str]) -> int:
    """Parse + write slot start/duration. Returns count of unparseable slots."""
    cur.execute("SELECT id, description FROM slots ORDER BY id")
    rows = cur.fetchall()
    unparseable = 0
    for slot_id, description in rows:
        parsed = parse_slot_description(description)
        if parsed is None:
            unparseable += 1
            report.append(f"SLOT {slot_id}: unparseable description {description!r}")
            continue
        cur.execute(
            "UPDATE slots SET start_time = %s, duration_minutes = %s WHERE id = %s",
            (parsed.start_time, parsed.duration_minutes, slot_id),
        )
    return unparseable


def snapshot_bookings(cur: psycopg.Cursor) -> int:
    """Copy each booking's time from its (now-parsed) slot. Returns rows updated."""
    cur.execute(
        """
        UPDATE bookings b
           SET start_time = s.start_time,
               duration_minutes = s.duration_minutes
          FROM slots s
         WHERE b.slot_id = s.id
           AND s.start_time IS NOT NULL
           AND b.start_time IS NULL
        """
    )
    return cur.rowcount


def seed_plan_pricing(cur: psycopg.Cursor, report: list[str]) -> int:
    """Seed one plan_pricing row per plan at its predominant slot duration.

    Uses the plan's current price_paise/advance_paise. Idempotent: skips plans
    that already have an active row for that duration.
    """
    cur.execute("SELECT id, price_paise, advance_paise FROM plans")
    plans = cur.fetchall()
    seeded = 0
    for plan_id, price_paise, advance_paise in plans:
        cur.execute(
            """SELECT duration_minutes FROM slots
                WHERE plan_id = %s AND duration_minutes IS NOT NULL""",
            (plan_id,),
        )
        durations = [r[0] for r in cur.fetchall()]
        duration = Counter(durations).most_common(1)[0][0] if durations else 120
        cur.execute(
            """SELECT 1 FROM plan_pricing
                WHERE plan_id = %s AND duration_minutes = %s AND is_active""",
            (plan_id, duration),
        )
        if cur.fetchone() is not None:
            continue
        cur.execute(
            """INSERT INTO plan_pricing
                   (plan_id, duration_minutes, price_paise, advance_paise,
                    effective_from, effective_to, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, true)""",
            (plan_id, duration, price_paise, advance_paise, date(2020, 1, 1),
             date(2099, 12, 31)),
        )
        seeded += 1
        report.append(
            f"PLAN {plan_id}: seeded plan_pricing duration={duration} "
            f"price_paise={price_paise} advance_paise={advance_paise}"
        )
    return seeded


def overlap_precheck(cur: psycopg.Cursor, buffer_minutes: int, report: list[str]) -> int:
    """Report active bookings whose occupied windows overlap. Returns count.

    Uses buffer_minutes=0 by default to match the DB exclusion constraint, which
    guards USABLE-time overlap only (the cleaning buffer is a service-layer policy
    on new bookings, not a DB invariant). Pass a non-zero --buffer to preview the
    stricter policy if desired.
    """
    cur.execute(
        """
        SELECT id, location_id, plan_id, booking_date, start_time, duration_minutes
          FROM bookings
         WHERE status IN ('pending','accepted')
           AND start_time IS NOT NULL AND duration_minutes IS NOT NULL
        """
    )
    rows = cur.fetchall()

    def window(bd: date, st, dur: int) -> tuple[datetime, datetime]:
        anchor = datetime.combine(bd, st)
        return anchor, anchor + timedelta(minutes=dur + buffer_minutes)

    # Group by (location, plan, date); compare pairs within each group.
    groups: dict[tuple, list] = {}
    for bid, loc, plan, bd, st, dur in rows:
        groups.setdefault((loc, plan, bd), []).append((bid, window(bd, st, dur)))

    clashes = 0
    for key, items in groups.items():
        items.sort(key=lambda x: x[1][0])
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (a_id, (a_s, a_e)) = items[i]
                (b_id, (b_s, b_e)) = items[j]
                if a_s < b_e and b_s < a_e:
                    clashes += 1
                    report.append(
                        f"OVERLAP loc={key[0]} plan={key[1]} date={key[2]}: "
                        f"booking {a_id} [{a_s}..{a_e}) overlaps {b_id} [{b_s}..{b_e})"
                    )
    return clashes


def run(buffer_minutes: int, report_path: str) -> None:
    report: list[str] = []
    with psycopg.connect(_conninfo()) as conn:
        with conn.cursor() as cur:
            unparseable = backfill_slots(cur, report)
            updated = snapshot_bookings(cur)
            seeded = seed_plan_pricing(cur, report)
            clashes = overlap_precheck(cur, buffer_minutes, report)
        conn.commit()

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(report) + ("\n" if report else ""))

    print(f"slots unparseable:        {unparseable}")
    print(f"bookings snapshotted:     {updated}")
    print(f"plan_pricing seeded:      {seeded}")
    print(f"existing overlaps found:  {clashes}")
    print(f"report written to:        {report_path}")
    if unparseable or clashes:
        print(
            "\nACTION REQUIRED: resolve unparseable slots and/or overlapping "
            "bookings before running migration B (constraint enforcement)."
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill time-range slot data.")
    ap.add_argument(
        "--buffer",
        type=int,
        default=0,
        help="buffer minutes for the overlap pre-check (0 = match the DB "
        "constraint, which is usable-time only)",
    )
    ap.add_argument("--report", default="time_slots_retrofit_report.txt")
    args = ap.parse_args()
    run(args.buffer, args.report)


if __name__ == "__main__":
    main()
