"""Generate fix_migrated_totals.sql from a MariaDB dump of the old `booking` table.

The migration stored ``bookings.total_paise = old amount`` (base amount only).
The old app's real total was ``advanceamount + amountdue``. For every old booking
where those differ, this writes one row into a temp table; the generated SQL then
updates ``bookings`` from it, guarded so a booking is only changed if

  * its id exists and its booking_reference matches the dump, and
  * its total_paise still equals the migrated value (old amount x 100),

so bookings already re-saved in the admin panel, or rows created later in the new
app that merely reuse an id, are never touched. The SQL prints how many rows it
found and matched before updating.

Usage (from the repo root):
    py New_Application/scripts/migrate_from_mariadb/gen_total_fix.py \
        New_Application/scripts/cine_celebration_data.sql \
        New_Application/scripts/migrate_from_mariadb/fix_migrated_totals.sql \
        --date-through 2026-11-13

``--date-through`` keeps only bookings whose celebration date (old ``date``) is on
or before that date, so future bookings are left alone. ``--created-before`` can
additionally restrict by the old ``createts`` (for example the cutover day).

Standard library only. Read-only on the dump.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_INSERT_RE = re.compile(r"INSERT INTO `booking` \(([^)]*)\) VALUES", re.IGNORECASE)
_BATCH = 500


def _parse_values(text: str, pos: int) -> tuple[list[list[object]], int]:
    """Parse ``(v,v,...),(...);`` starting at ``pos``. Returns (rows, end_pos)."""
    rows: list[list[object]] = []
    n = len(text)
    while pos < n:
        # Skip to the next '(' or stop at ';'.
        while pos < n and text[pos] not in "(;":
            pos += 1
        if pos >= n or text[pos] == ";":
            return rows, pos + 1
        pos += 1  # past '('
        row: list[object] = []
        while True:
            while text[pos] in " \t\r\n":
                pos += 1
            ch = text[pos]
            if ch == "'":
                pos += 1
                buf: list[str] = []
                while True:
                    c = text[pos]
                    if c == "\\":
                        buf.append(text[pos + 1])
                        pos += 2
                    elif c == "'":
                        if text[pos + 1] == "'":
                            buf.append("'")
                            pos += 2
                        else:
                            pos += 1
                            break
                    else:
                        buf.append(c)
                        pos += 1
                row.append("".join(buf))
            else:
                start = pos
                while text[pos] not in ",)":
                    pos += 1
                token = text[start:pos].strip()
                row.append(None if token.upper() == "NULL" else token)
            if text[pos] == ",":
                pos += 1
                continue
            pos += 1  # past ')'
            break
        rows.append(row)
    return rows, pos


def read_bookings(dump: Path) -> list[dict[str, object]]:
    text = dump.read_text(encoding="latin-1")
    bookings: list[dict[str, object]] = []
    for match in _INSERT_RE.finditer(text):
        cols = [c.strip().strip("`") for c in match.group(1).split(",")]
        rows, _ = _parse_values(text, match.end())
        for row in rows:
            if len(row) != len(cols):
                raise SystemExit(
                    f"column/value mismatch ({len(cols)} vs {len(row)}) near id {row[:1]}"
                )
            bookings.append(dict(zip(cols, row)))
    return bookings


def _int(value: object) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return 0


def _sql_str(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dump", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--created-before",
        default=None,
        help="YYYY-MM-DD: only bookings with createts before this date",
    )
    parser.add_argument(
        "--date-through",
        default=None,
        help="YYYY-MM-DD: only bookings whose celebration date is on or before this date",
    )
    args = parser.parse_args()

    bookings = read_bookings(args.dump)
    if not bookings:
        raise SystemExit("no booking rows found in the dump")
    ids = [_int(b["id"]) for b in bookings]

    in_scope = [
        b
        for b in bookings
        if (args.created_before is None or str(b["createts"]) < args.created_before)
        and (args.date_through is None or str(b["date"]) <= args.date_through)
    ]

    rows: list[tuple[int, str, int, int]] = []  # id, ref, old_total, new_total
    skipped: list[str] = []
    for b in in_scope:
        total_old = _int(b["advanceamount"]) + _int(b["amountdue"])
        amount = _int(b["amount"])
        if total_old == amount:
            continue
        if total_old <= 0 < amount:
            # advanceamount and amountdue are both 0 although the booking had an
            # amount: the old figures were never filled in. Setting the total to 0
            # would hide a real booking, so leave it and list it for review.
            skipped.append(
                f"--   id {_int(b['id'])}: amount {amount}, status {b['statusid']}, "
                f"date {b['date']}"
            )
            continue
        rows.append((_int(b["id"]), str(b["bookingreference"]), amount * 100, total_old * 100))

    cutoff = (
        f"celebration date on or before {args.date_through or 'any'}, "
        f"created before {args.created_before or 'any'}"
    )
    lines = [
        "-- Generated by gen_total_fix.py from the old booking dump. Do not edit by hand.",
        f"-- Dump rows: {len(bookings)} (ids {min(ids)}..{max(ids)}); in scope "
        f"({cutoff}): {len(in_scope)}; rows to fix: {len(rows)}.",
        "-- Only bookings whose id AND booking_reference match and whose total is still",
        "-- the migrated value (old amount x 100) are updated.",
        "-- Back up first (pg_dump) and run fix_advance_gap_4_bookings.sql first. See",
        "-- FIX_MIGRATED_TOTALS.md.",
        "",
        f"-- NOT UPDATED ({len(skipped)}): old advanceamount and amountdue were both 0 but",
        "-- amount > 0, so the real total is unknown. They keep total = old amount.",
        "-- Review by hand:",
        *skipped,
        "",
        "BEGIN;",
        "",
        "CREATE TEMP TABLE fix_totals (",
        "    id bigint, ref text, old_total bigint, new_total bigint",
        ") ON COMMIT DROP;",
        "",
    ]
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start : start + _BATCH]
        values = ",\n".join(
            f"  ({i}, {_sql_str(ref)}, {old}, {new})" for i, ref, old, new in chunk
        )
        lines.append(f"INSERT INTO fix_totals VALUES\n{values};")
        lines.append("")
    lines += [
        "-- What will be touched (check these before COMMIT would matter):",
        "SELECT count(*)                                              AS rows_in_file,",
        "       count(b.id)                                           AS found_in_db,",
        "       count(*) FILTER (WHERE b.booking_reference = f.ref)   AS reference_matches,",
        "       count(*) FILTER (WHERE b.booking_reference = f.ref",
        "                          AND b.total_paise = f.old_total)   AS will_update",
        "FROM fix_totals f LEFT JOIN bookings b ON b.id = f.id;",
        "",
        "UPDATE bookings b",
        "SET total_paise = f.new_total",
        "FROM fix_totals f",
        "WHERE b.id = f.id",
        "  AND b.booking_reference = f.ref",
        "  AND b.total_paise = f.old_total;",
        "",
        "-- Sanity: migrated bookings still overpaid after the fix (expect 0 or a few).",
        "SELECT count(*) AS still_overpaid FROM bookings b",
        "JOIN (SELECT booking_id, SUM(amount_paise) AS paid FROM payments",
        "      GROUP BY booking_id) p ON p.booking_id = b.id",
        "WHERE p.paid > b.total_paise",
        "  AND b.id IN (SELECT booking_id FROM payments WHERE note LIKE 'migrated%');",
        "",
        "COMMIT;",
        "",
    ]
    args.out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"dump rows: {len(bookings)} (ids {min(ids)}..{max(ids)})")
    print(f"in scope ({cutoff}): {len(in_scope)}")
    print(f"rows to fix: {len(rows)} -> {args.out}")
    print(f"skipped for manual review (advance=0, due=0, amount>0): {len(skipped)}")


if __name__ == "__main__":
    main()
