# Database Restore Runbook

Restores a PostgreSQL backup produced by `backup.sh` (gzipped `pg_dump`,
stored in the private R2 bucket under `backups/daily/` or `backups/weekly/`).

## Prerequisites

- The `deploy/` stack is running (`docker compose up -d`) or at least the
  `postgres` service is up.
- `aws` CLI configured for the R2 endpoint, or the object downloaded manually.
- Environment: `POSTGRES_USER`, `POSTGRES_DB`, `R2_PRIVATE_BUCKET`,
  `R2_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

## Steps

1. Pick the backup to restore and download it:

   ```bash
   aws --endpoint-url "$R2_ENDPOINT_URL" s3 cp \
     "s3://$R2_PRIVATE_BUCKET/backups/daily/2025-12-25.sql.gz" /tmp/restore.sql.gz
   ```

2. (Destructive) Drop and recreate the target database, or restore into a fresh
   one. To restore into the existing DB, first stop the API so no writes occur:

   ```bash
   docker compose stop api
   ```

3. Restore the dump through the postgres container:

   ```bash
   gunzip -c /tmp/restore.sql.gz | \
     docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
   ```

4. Bring migrations up to head (in case the dump predates a schema change) and
   restart the API:

   ```bash
   docker compose run --rm api alembic upgrade head
   docker compose start api
   ```

5. Verify: hit `GET /healthz`, spot-check a few bookings, and confirm row counts
   look right.

## Test restores

Perform a test restore into a throwaway database at least once (and after any
major schema change) to confirm this runbook works end to end.
