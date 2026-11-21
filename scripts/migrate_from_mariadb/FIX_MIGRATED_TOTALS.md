# Fix totals of migrated bookings

## Problem
The migration stored `bookings.total_paise = old amount`. In the old app,
`amount` was only the base amount; the real total was
`amount + foodamount + otheramount + cleaningcharge - discount`, which equals
`advanceamount + amountdue` (what staff saw). Payments were migrated correctly,
so migrated bookings with extras show a total that is too low and a wrong amount
due. Saving a booking in the admin panel recalculates it, but that re-prices with
TODAY's catalog, so fix the data directly instead.

## Source data
`New_Application/scripts/cine_celebration_data.sql`, a phpMyAdmin dump generated
14 Nov 2026 09:18: 3,164 bookings (ids 1..3164). Only bookings whose CELEBRATION
date is on or before 13 Nov 2026 (3,129 of them) are fixed; upcoming bookings
are left alone.

Checks on those 3,129 bookings:
- 2,685 have `advanceamount + amountdue <> amount`. All but 4 are explained by
  food/other/cleaning/discount (for example `otheramount = 1` was used to round
  1999 up to 2000). The 4 exceptions are ids 5, 198, 210, 1076; for them the old
  app's own figure (`advanceamount + amountdue`) is used.
- 34 bookings (30 accepted, 4 rejected) have `advanceamount = 0` AND
  `amountdue = 0` while `amount > 0`. Their real total is unknown, so they are
  NOT updated and are listed at the top of the generated file for manual review.
- Paid vs old `advanceamount`: only ids 1209, 1218, 1278, 2380 differ, and they
  are fixed by `fix_advance_gap_4_bookings.sql`.

## The generated file
`fix_migrated_totals.sql` (2,651 rows) is produced by:

```bash
py New_Application/scripts/migrate_from_mariadb/gen_total_fix.py \
   New_Application/scripts/cine_celebration_data.sql \
   New_Application/scripts/migrate_from_mariadb/fix_migrated_totals.sql \
   --date-through 2026-11-13
```

It loads the rows into a temp table and updates `bookings` from it in one
transaction. A booking is changed only if its id AND `booking_reference` match
the dump and its total still equals the migrated value (old amount x 100). So
bookings already re-saved in the admin panel, and new-app bookings that merely
reuse an id, are never touched. Before updating it prints:

| column | meaning |
|---|---|
| rows_in_file | rows in the fix |
| found_in_db | ids that exist in the new DB |
| reference_matches | of those, the reference matches |
| will_update | of those, total is still the migrated value |

`will_update` is the number of bookings that are changed; the UPDATE then reports
`UPDATE <that number>`. A big gap between `rows_in_file` and `will_update` means
bookings were skipped (already re-saved, id not migrated, or reference regenerated
on collision); that is safe, and you can investigate the difference.

## Run order (droplet, from `~/Cinematic-Celebration-Apps/deploy`)
1. `git pull` (main containing these files).
2. Back up:
   ```bash
   mkdir -p ~/backups
   docker compose --env-file ../.env exec -T postgres \
     pg_dump -U cinematic cinematic > ~/backups/pre-total-fix-$(date +%F-%H%M).sql
   ```
3. Paid fix for 4 bookings FIRST:
   ```bash
   docker compose --env-file ../.env exec -T postgres \
     psql -U cinematic -d cinematic -v ON_ERROR_STOP=1 \
     < ../scripts/migrate_from_mariadb/fix_advance_gap_4_bookings.sql
   ```
4. Totals fix:
   ```bash
   docker compose --env-file ../.env exec -T postgres \
     psql -U cinematic -d cinematic -v ON_ERROR_STOP=1 \
     < ../scripts/migrate_from_mariadb/fix_migrated_totals.sql
   ```
   Read the counts table, then `UPDATE n`, then `still_overpaid` (should be 0 or a
   few genuinely overpaid bookings).

## Verify
Open an old booking WITHOUT saving: amount due should match what the old app
showed. Spot-check ids 1209 (total 2000), 1076 (total 2499) and one booking with
food/cleaning charges. Then re-run your March collected report.

## Rollback
Restore the `pg_dump` from step 2.
