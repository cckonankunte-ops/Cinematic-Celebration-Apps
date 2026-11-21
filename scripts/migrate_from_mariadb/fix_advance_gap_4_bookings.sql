-- One-off data fix: 4 migrated bookings whose old `advanceamount` was higher
-- than cashadvance + upipayment (+ onlinepayment). The migration only rebuilt
-- payments from those per-method columns, so the new ledger is short.
--
-- Fix: append ONE corrective UPI payment per booking so the ledger total equals
-- the old advanceamount (the ledger is append-only, so we add, never edit).
--
--   id    old advanceamount  migrated paid  correction (UPI)
--   1209  2000               1000            +1000
--   1218  2850               1000            +1850
--   1278  1000                500            + 500
--   2380  1000                350            + 650   (rejected booking)
--
-- Guarded and idempotent: a booking is only touched if its CURRENT paid total is
-- exactly the migrated value above and it has no adjustment row yet. Running it
-- twice, or on a booking that was edited since, inserts nothing.
--
-- HOW TO RUN (on the droplet, from ~/Cinematic-Celebration-Apps/deploy):
--   1. Back up first:
--        docker compose --env-file ../.env exec -T postgres \
--          pg_dump -U cinematic cinematic > ~/backups/pre-advance-fix-$(date +%F-%H%M).sql
--   2. Preview (read-only) - run only the SELECT below and check the 4 rows.
--   3. Apply:
--        docker compose --env-file ../.env exec -T postgres \
--          psql -U cinematic -d cinematic -v ON_ERROR_STOP=1 \
--          < ../scripts/migrate_from_mariadb/fix_advance_gap_4_bookings.sql

-- ---- PREVIEW (read-only) ---------------------------------------------------
SELECT b.id, b.booking_reference, b.status,
       COALESCE(p.paid, 0) / 100.0 AS paid_now,
       v.target_paise / 100.0      AS target
FROM (VALUES
        (1209::bigint, 100000::bigint, 200000::bigint),
        (1218, 100000, 285000),
        (1278,  50000, 100000),
        (2380,  35000, 100000)
     ) AS v(id, expected_paid_paise, target_paise)
JOIN bookings b ON b.id = v.id
LEFT JOIN (SELECT booking_id, SUM(amount_paise) AS paid
           FROM payments GROUP BY booking_id) p ON p.booking_id = b.id
ORDER BY b.id;

-- ---- APPLY -----------------------------------------------------------------
BEGIN;

INSERT INTO payments
    (booking_id, method, amount_paise, received_at, provider, provider_ref, note)
SELECT b.id,
       'upi',
       v.target_paise - COALESCE(p.paid, 0),
       b.created_at,
       NULL,
       NULL,
       'migrated adjustment: match old advanceamount'
FROM (VALUES
        (1209::bigint, 100000::bigint, 200000::bigint),
        (1218, 100000, 285000),
        (1278,  50000, 100000),
        (2380,  35000, 100000)
     ) AS v(id, expected_paid_paise, target_paise)
JOIN bookings b ON b.id = v.id
LEFT JOIN (SELECT booking_id, SUM(amount_paise) AS paid
           FROM payments GROUP BY booking_id) p ON p.booking_id = b.id
WHERE COALESCE(p.paid, 0) = v.expected_paid_paise
  AND NOT EXISTS (
        SELECT 1 FROM payments x
        WHERE x.booking_id = b.id
          AND x.note LIKE 'migrated adjustment%'
      );

-- Verify: every row should now show paid = target.
SELECT b.id, b.booking_reference,
       COALESCE(SUM(p.amount_paise), 0) / 100.0 AS paid_after
FROM bookings b
LEFT JOIN payments p ON p.booking_id = b.id
WHERE b.id IN (1209, 1218, 1278, 2380)
GROUP BY b.id, b.booking_reference
ORDER BY b.id;

COMMIT;
