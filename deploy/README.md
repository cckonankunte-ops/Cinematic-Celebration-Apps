# Deployment

Single small VPS running Docker Compose: **API + PostgreSQL + Caddy** (automatic
HTTPS). The customer site and admin panel are static builds served from
Cloudflare Pages; public images come from a public R2 bucket on a CDN domain.

## Prerequisites

- Docker + Docker Compose on the VPS.
- DNS: `api.cinematiccelebration.in` → the VPS public IP (Caddy gets TLS certs).
- `New_Application/.env` filled in from `New_Application/.env.example`.

## First deploy / upgrades

Run migrations to completion **before** the API workers start, so no worker ever
serves against an old schema:

```bash
cd New_Application/deploy
docker compose build api
docker compose run --rm api alembic upgrade head   # must succeed
docker compose up -d                                # api + postgres + caddy
```

Check health: `curl https://api.cinematiccelebration.in/healthz` → `{"status":"ok"}`.

## Cron jobs

Install the host crontab (edit the repo path first):

```bash
mkdir -p /var/log/cc
crontab New_Application/deploy/cron/crontab
```

- `expire_pending` runs every minute inside the API container.
- Nightly backup runs `backup/backup.sh` at 02:00 IST.

Make the backup script executable once: `chmod +x deploy/backup/backup.sh`.

## Memory budget (1–2 GB VPS)

| Service  | mem_limit |
|----------|-----------|
| postgres | 300 MB (shared_buffers 64MB, max_connections 20) |
| api      | 220 MB (uvicorn, 2 workers) |
| caddy    | 40 MB |

SQLAlchemy pool is `pool_size=3, max_overflow=2` per worker → ≤10 connections
for 2 workers, within `max_connections=20`.

## Backups & restore

Nightly `pg_dump` → gzip → private R2 bucket (14 daily + 8 weekly). Restore
procedure: see `backup/RESTORE.md` (test-restore at least once).

## Static frontends

Build and deploy to Cloudflare Pages from `apps/admin` and `apps/web`:

```bash
# admin
cd New_Application/apps/admin && npm ci && npm run gen:api && npm run build   # -> dist/
# web
cd New_Application/apps/web && npm ci && npm run build                         # -> dist/
```

Set `VITE_API_BASE_URL` (admin) and `PUBLIC_API_BASE_URL` (web) to
`https://api.cinematiccelebration.in` at build time, and ensure both site
origins are in the API `CORS_ALLOWED_ORIGINS`.
