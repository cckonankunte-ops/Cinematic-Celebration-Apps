# Fix totals of migrated bookings

## Problem
The migration stored `bookings.total_paise = old amount`. In the old app,
`amount` was only the base amount; the real total was
`amount + foodamount + otheramount + cleaningcharge - discount`, which equals
`advanceamount + amountdue` (what staff saw). Payments were migrated correctly,
so migrated bookings with extras show a total that is too low and a wrong amount
due. Saving a booking in the admin panel recalculates it, but that re-prices with
TODAY's catalog, so fix the data directly instead.

Checks on the old data (2,833 bookings in the dump):
- 2,431 bookings have `advanceamount + amountdue <> amount`. 2,427 are fully
  explained by food/other/cleaning/discount (for example `otheramount = 1` was
  used to round 1999 up to 2000). The other 4 (ids 5, 198, 210, 1076) are the
  ones the old-DB check found.
- 28 bookings have `advanceamount = 0` AND `amountdue = 0` while `amount > 0`
  (27 accepted, 1 rejected). Their real total is unknown, so they are NOT
  updated and are listed at the top of the generated file for manual review.

## The generated file
`fix_migrated_totals.sql` (2,403 guarded UPDATEs) was produced from
`Old_Application/cine_celebration_data.sql` by:

```bash
py New_Application/scripts/migrate_from_mariadb/gen_total_fix.py \
   Old_Application/cine_celebration_data.sql \
   New_Application/scripts/migrate_from_mariadb/fix_migrated_totals.sql
```

Each statement is `UPDATE bookings SET total_paise = <new> WHERE id = <id> AND
total_paise = <old amount x 100>`. A booking is only changed if it still holds the
migrated total, so bookings already re-saved in the admin panel are skipped, and
ids missing from the new DB update 0 rows. The file runs in one transaction.

The dump is dated 4 Oct 2026 (latest `createts` 2026-10-04 03:00). Old bookings
created after that are not in it. Compare `SELECT COUNT(*), MAX(id) FROM booking`
on the old DB with the dump (2,833 rows, max id 2833).

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
   psql prints `UPDATE 1` for each changed booking (`UPDATE 0` for a skipped
   one) and then `still_overpaid`, which should be 0 or a few genuinely
   overpaid bookings.

## Verify
Open an old booking WITHOUT saving: amount due should match what the old app
showed. Spot-check ids 1209 (total 2000), 1076 (total 2499) and one booking with
food/cleaning charges. Then re-run your March collected report.

## Rollback
Restore the `pg_dump` from step 2.
