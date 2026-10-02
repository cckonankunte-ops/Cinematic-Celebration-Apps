#!/usr/bin/env bash
# Nightly PostgreSQL backup -> gzip -> Cloudflare R2 (private bucket).
# Run from the deploy/ directory (see deploy/cron/crontab).
# Retention: 14 daily + 8 weekly (weekly kept on Sundays). Enforced by lifecycle
# rules on the R2 bucket OR by the prune step below.
set -euo pipefail

# --- Config from environment (.env sourced by the caller or exported) ---
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_DB:=cinematic}"
: "${R2_PRIVATE_BUCKET:=cinematic-backups}"
: "${R2_ENDPOINT_URL:?R2_ENDPOINT_URL is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

DATE="$(date -u +%F)"
DOW="$(date -u +%u)"   # 1=Mon .. 7=Sun
TMP="/tmp/cc-${DATE}.sql.gz"

# Dump via the running postgres container (no host psql needed).
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" \
  | gzip > "${TMP}"

# Upload: always to daily/, and on Sundays also to weekly/.
aws --endpoint-url "${R2_ENDPOINT_URL}" s3 cp "${TMP}" \
  "s3://${R2_PRIVATE_BUCKET}/backups/daily/${DATE}.sql.gz"
if [ "${DOW}" = "7" ]; then
  aws --endpoint-url "${R2_ENDPOINT_URL}" s3 cp "${TMP}" \
    "s3://${R2_PRIVATE_BUCKET}/backups/weekly/${DATE}.sql.gz"
fi

rm -f "${TMP}"
echo "backup complete: ${DATE} (dow=${DOW})"
