# Deployment

Single small VPS running Docker Compose: **API + PostgreSQL + Caddy** (automatic
HTTPS). The customer site and admin panel are static builds on **Cloudflare
Pages**; public images + nightly backups live in **Cloudflare R2**. Only the
API + Postgres run on the paid VPS — everything else is free on Cloudflare.

> Full rationale, hosting decision, and the detailed step-by-step is in the spec:
> `.kiro/specs/production-deployment/design.md`. This README is the operational
> quick-reference.

## Rollout model (trial-first)

1. **Trial:** deploy to temporary staging URLs and run ~1 week in parallel with
   the untouched live legacy site.
   - API: `api-staging.cinematiccelebration.in` (one new A record; the live apex
     and `admin.` are NOT touched).
   - Frontends: free Cloudflare Pages `*.pages.dev` URLs.
   - Cross-site during the trial → cookies `SameSite=None; Secure`.
2. **Review & fix** on staging; conclude on explicit sign-off.
3. **Cutover:** link the real domains and repoint the apex away from Hostinger
   LAST; cookies become `SameSite=Lax`. Reversible via recorded legacy DNS.

## Hosting

- **Production:** cheapest reliable **1 GB India-region VPS** (CloudPe ~₹350/mo,
  or Vultr Bangalore / DO BLR1 ~₹450-550/mo), Ubuntu 24.04 LTS, x86_64, annual
  prepay. NOT Oracle (no SLA / reclaim risk).
- **1 GB guardrails:** add a 1 GB swap file; **build the API image OFF the box**
  (Codespace/CI → push to a registry) and `docker compose pull` on the VPS —
  building on a 1 GB box can OOM-kill Postgres.

## Prerequisites

- Docker + Docker Compose on the VPS; a non-root `deploy` user in the `docker`
  group; ufw allowing SSH/80/443.
- DNS A record for the API host (`api-staging` during trial, `api` after cutover)
  → the VPS IP (Caddy gets TLS automatically).
- `New_Application/.env` filled from `New_Application/.env.example` (never commit
  `.env`). Set `API_HOST`, `API_IMAGE`, DB creds, `JWT_SECRET`, CORS, cookie
  policy, R2 + AWS backup creds, `MANUAL_UPI_VPA`. Leave `SMTP_*` blank (email
  disabled this phase).

## First deploy / upgrades (pull-based)

Build the image off-box and push it; then on the VPS, from `New_Application/deploy`:

```bash
docker compose pull                               # fetch the prebuilt API image
docker compose run --rm api alembic upgrade head  # MUST succeed before workers
docker compose up -d                              # api + postgres + caddy
curl https://$API_HOST/healthz                    # -> {"status":"ok"}
```

If `alembic upgrade head` fails, stop — do not start workers.

## Seed minimal data (fresh environment only)

Enough to log in and smoke-test (NOT the real data import — that is the separate
data-migration spec):

```bash
SEED_ADMIN_USERNAME=owner SEED_ADMIN_PASSWORD='<strong>' \
  docker compose run --rm api python -m app.jobs.seed_min
```

Idempotent: creates the admin/staff roles, one admin user (argon2-hashed), the 3
branches, and a minimal bookable plan+slot. Safe to re-run.

## Cron jobs

```bash
mkdir -p /var/log/cc
chmod +x deploy/backup/backup.sh
crontab deploy/cron/crontab      # edit the repo path inside it first
```

- `expire_pending` runs every minute inside the API container (idempotent).
- Nightly backup runs `backup/backup.sh` at 02:00 IST.

## Memory budget (1 GB VPS)

| Service  | mem_limit |
|----------|-----------|
| postgres | 300 MB (shared_buffers 64MB, max_connections 20) |
| api      | 220 MB (uvicorn, 2 workers) |
| caddy    | 40 MB |

≈ 560 MB total + a 1 GB swap safety net. SQLAlchemy pool `pool_size=3,
max_overflow=2` per worker → ≤10 connections for 2 workers (< `max_connections=20`).
Watch `docker stats`; sustained swap or an OOM → resize to 2 GB.

## Backups & restore

Nightly `pg_dump` → gzip → private R2 bucket (14 daily + 8 weekly). Perform a
restore drill into a scratch DB at least once — see `backup/RESTORE.md`.

## Static frontends (Cloudflare Pages)

```bash
# admin
cd New_Application/apps/admin && npm ci && npm run build   # -> dist/
# web
cd New_Application/apps/web && npm ci && npm run build      # -> dist/
```

Set `VITE_API_BASE_URL` (admin) and `PUBLIC_API_BASE_URL` (web) at build time:
the staging API URL during the trial, `https://api.cinematiccelebration.in` after
cutover. Keep both site origins in the API `CORS_ALLOWED_ORIGINS`.

## Cutover (after trial sign-off)

Lower DNS TTLs and record the legacy DNS values first. Then: add `A api`, set
`API_HOST=api.cinematiccelebration.in` + redeploy; attach Pages custom domains
(admin → `admin.`, web → apex/`www`); rebuild frontends with the production API
URL; set `COOKIE_SAMESITE=lax`, `ENVIRONMENT=production`, real `CORS_ALLOWED_ORIGINS`;
repoint the apex + `admin.` away from Hostinger LAST; move the uptime monitor to
`api.`. Rollback = restore the recorded legacy DNS.
