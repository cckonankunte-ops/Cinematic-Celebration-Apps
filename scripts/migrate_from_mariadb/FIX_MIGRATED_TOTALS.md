# Fix totals of migrated bookings

## Problem
The migration stored `bookings.total_paise = old amount`. In the old app,
`amount` was only the base amount; the real total was
`amount + foodamount + otheramount + cleaningcharge - discount`, which equals
`advanceamount + amountdue` (what staff saw). Payments were migrated correctly,
so migrated bookings with extras show a total that is too low and a negative
(or wrong) amount due. Saving a booking in the admin panel recalculates it, but
that re-prices with TODAY's catalog, so fix the data directly instead.

A check on the old DB found only 4 rows (ids 5, 198, 210, 1076) where
`amount + extras - discount` differs from `advanceamount + amountdue`. We use
`advanceamount + amountdue` for all rows (the old app's own figure).

Run `fix_advance_gap_4_bookings.sql` FIRST (it corrects paid on 4 bookings), so
paid and total are both right afterwards.

## Step 1 - generate the UPDATE statements (old MariaDB, phpMyAdmin)
```sql
SELECT CONCAT('UPDATE bookings SET total_paise=', (advanceamount + amountdue) * 100,
              ' WHERE id=', id, ' AND total_paise=', amount * 100, ';') AS stmt
FROM booking
WHERE (advanceamount + amountdue) <> amount;
```
Each statement only changes a booking whose total is STILL the migrated value
(`total_paise = amount * 100`). Bookings you already re-saved in the admin panel
have a different total, so they are skipped automatically. Ids that do not exist
in the new DB update 0 rows.

Copy the `stmt` column (phpMyAdmin: "Copy to clipboard" or Export as text).

## Step 2 - save them in a file on the droplet
```bash
mkdir -p ~/backups
cat > ~/fix_totals.sql <<'EOF'
BEGIN;
-- paste the generated UPDATE statements here
-- sanity check inside the transaction (migrated bookings now overpaid?):
SELECT count(*) AS still_overpaid FROM bookings b
JOIN (SELECT booking_id, SUM(amount_paise) paid FROM payments GROUP BY booking_id) p
  ON p.booking_id = b.id
WHERE p.paid > b.total_paise AND b.id IN (SELECT booking_id FROM payments WHERE note LIKE 'migrated%');
COMMIT;
EOF
```
Edit the file (`nano ~/fix_totals.sql`) and paste the statements between BEGIN and
the SELECT.

## Step 3 - back up, then apply
```bash
cd ~/Cinematic-Celebration-Apps/deploy
docker compose --env-file ../.env exec -T postgres \
  pg_dump -U cinematic cinematic > ~/backups/pre-total-fix-$(date +%F-%H%M).sql
docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic -v ON_ERROR_STOP=1 < ~/fix_totals.sql
```
psql prints `UPDATE n` for each statement. `still_overpaid` should be 0 or a
handful of rows that were genuinely overpaid in the old system.

## Verify
Open an old booking WITHOUT saving: amount due should match what the old app
showed. Spot-check ids 1209, 1218, 1278 (also covered by the advance fix) and
one booking with food/cleaning charges.

## Rollback
Restore the `pg_dump` from step 3, or re-run with totals set back to
`amount * 100` (swap the two numbers in each statement).
