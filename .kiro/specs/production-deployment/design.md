# Design — Production Deployment (trial-first)

## Overview

This design is the **go-live runbook** for taking Phase 1 to production for the
first time, in two phases:

1. **Trial phase** — deploy the full new system to temporary staging URLs and run
   it in parallel with the untouched live legacy site for ~1 week of open review.
2. **Cutover phase** — after sign-off, link the real domains and repoint the apex
   away from the legacy system as the final, reversible step.

It builds on the existing `New_Application/deploy/` scaffolding
(`docker-compose.yml`, `Caddyfile`, `cron/crontab`, `backup/backup.sh`,
`README.md`) and changes as little as possible. The only code/scaffolding edits
this design calls for are: (a) parameterising the Caddy host so it can be
`api-staging` during the trial and `api` after cutover, and (b) confirming the
email no-op (already true — see "Email" below, no change needed).

### Target topology

```
                         Cloudflare (DNS + Pages + R2)
   Customer  ──►  Customer_Site (Astro)   ── *.pages.dev (trial) / apex (after)
   Staff     ──►  Admin_Site (React/Vite) ── *.pages.dev (trial) / admin. (after)
                         │  XHR (credentials: include)
                         ▼
             https://api-staging.cinematiccelebration.in   (trial)
             https://api.cinematiccelebration.in           (after cutover)
                         │
                   ┌─────▼──────── VPS (Docker Compose) ───────────┐
                   │  Caddy :80/:443  ──►  API (uvicorn :8000, x2)  │
                   │                         │                      │
                   │                     PostgreSQL 16  (volume)    │
                   └────────────────────────────────────────────────┘
                         │ nightly pg_dump           ▲ images (public)
                         ▼                            │
                   R2 private backups          R2 public images (img. CDN)
```

Legacy (untouched during trial): `cinematiccelebration.in` +
`admin.cinematiccelebration.in` on Hostinger (Node + MariaDB).

---

## Phase A — Provision the VPS (Req 1)

**Hosting decision (finalised — cost is the hard constraint):** a single
**cheap, reliable 1 GB VPS in an India region**, rupee billing, **annual prepay**
for the discount. Candidates: an Indian provider (e.g. CloudPe ~₹350/mo) or
**Vultr Bangalore / DigitalOcean BLR1** (~₹450-550/mo) for a more proven option.
Ubuntu 24.04 LTS, x86_64 (avoid ARM so no multi-arch image concerns). Hetzner
dropped (2026 price rises, no India region). Oracle Always Free (₹0) was
considered and **rejected for production** (no SLA + instances can be reclaimed/
throttled + ARM + capacity lottery) — unacceptable risk for a payment-taking
site when ~₹500/mo is affordable. Oracle Free is acceptable ONLY as an optional
throwaway staging/trial box, never for production. Decision: run production on
the paid VPS and do NOT migrate to Oracle even if a slot later opens; the ₹500
buys reliability and simplicity.

> **Cost framing (important).** Only the **API + PostgreSQL** run on this paid
> VPS. The customer site (Astro) and admin panel (React) are FREE on Cloudflare
> Pages, and images + backups are on Cloudflare R2 (free tier). So the entire
> new-app hosting bill is just this one ~₹350-500/mo VPS — not the ₹1000 that a
> 2 GB box would cost. GST reclaim is NOT available (owner is on GST composite
> @6%), so the sticker price is the real price; annual prepay is the main lever.
> Resize to 2 GB later ONLY if busy-day latency / OOM / ad bursts demand it.

**Size: start at 1 GB, resize to 2 GB when volume/ads grow (owner decision).**
Rationale: current volume is tens of bookings/day = "low"; the booking page is a
static Cloudflare Pages site and images are on R2/CDN, so an ad spike mostly hits
Cloudflare, NOT the VPS — the box only serves the lighter API calls. Container
idle footprint ≈ 560 MB (pg 300m / api 220m / caddy 40m), so 1 GB is workable
with the guardrails below. Resizing up to 2 GB (~$10-12/mo) on Vultr/DO takes
minutes and is reversible, so this is a safe lean start, not a lock-in.

> Budget note: 1 GB keeps infra within the ~$7/mo steering target. Moving to
> 2 GB later is a deliberate, documented exception to be taken only when real
> demand (busy-day latency, OOM events, or regular ad bursts) justifies it.

**1 GB guardrails (MUST do):**
1. **Add a swap file** (e.g. 1 GB) as an overflow safety net so a transient spike
   doesn't OOM-kill Postgres:
   ```bash
   fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile \
     && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab
   ```
   Swap is a safety net only; steady-state load must fit in RAM (Postgres hates
   living in swap).
2. **Build images OFF the box.** Do NOT run `docker compose build` on a 1 GB VPS
   (the build can OOM-kill Postgres). Build in the Codespace/CI and push an image
   to a registry (e.g. GHCR), then `docker compose pull` + `up -d` on the VPS. If
   building on-box is unavoidable, stop the api/postgres containers first, build,
   then start.
3. **Watch memory after go-live:** `docker stats` + the swap usage. Sustained
   swap use or any OOM kill is the signal to resize to 2 GB.

1. Create the server; add your SSH public key at creation (key-based auth only).
2. Create a non-root deploy user and give it Docker rights:
   ```bash
   adduser deploy && usermod -aG sudo deploy
   # after Docker is installed:
   usermod -aG docker deploy
   ```
3. Install Docker Engine + Compose plugin (official convenience script or distro
   docs). Verify `docker compose version`.
4. Firewall (ufw): allow SSH + 80 + 443, deny the rest.
   ```bash
   ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
   ```
5. Harden SSH: disable password auth and root login in `/etc/ssh/sshd_config`
   (`PasswordAuthentication no`, `PermitRootLogin no`), reload sshd.
6. Clone the repo under the deploy user, e.g. `/opt/cinematic` →
   `/opt/cinematic/Cinematic-Celebration-Apps` (the cron paths assume
   `/opt/cinematic/New_Application/deploy`; adjust to the real checkout path).

Memory fit: api 220m + postgres 300m + caddy 40m ≈ 560m, well under 4 GB (and
within a 1–2 GB box too). Cost stays < $7/mo.

---

## Phase B — DNS + HTTPS for the API (staging) (Req 2)

1. In the domain's DNS, add ONE record: `A  api-staging  → <VPS_IP>`. This does
   not affect the live apex or `admin.` records.
2. Parameterise the Caddy host. Change `deploy/Caddyfile` to read the hostname
   from an env var so the same file serves staging then production:
   ```
   {$API_HOST} {
       encode gzip
       reverse_proxy api:8000
   }
   ```
   and pass `API_HOST` to the caddy service in `docker-compose.yml`
   (`environment: [ "API_HOST=${API_HOST}" ]`). Set `API_HOST=api-staging.cinematiccelebration.in`
   in `.env` during the trial. (Caddy supports env substitution in the Caddyfile.)
3. Caddy auto-obtains a Let's Encrypt cert on first start once DNS resolves and
   80/443 are open. HTTP → HTTPS redirect is automatic.
4. Verify: `curl https://api-staging.cinematiccelebration.in/healthz` → `{"status":"ok"}`.

> Note: the current `Caddyfile` hardcodes `api.cinematiccelebration.in`. The
> env-var change above is the one scaffolding edit needed; after cutover we just
> change `API_HOST` and reload Caddy (no code edit).

---

## Phase C — Cloudflare: account, R2, Pages (Req 3)

1. Create a Cloudflare account; add the `cinematiccelebration.in` zone (this does
   NOT require moving nameservers yet if you only use Pages `*.pages.dev` during
   the trial — but adding the zone now is convenient for R2 + later custom
   domains). Keep existing legacy DNS records intact in the zone.
2. **R2 buckets:**
   - Public images bucket (e.g. `cinematic-public`), exposed via a CDN custom
     domain `img.cinematiccelebration.in` (add that CNAME; harmless new subdomain).
   - Private backups bucket (e.g. `cinematic-backups`), not public.
   - Create an R2 API token (access key + secret) for boto3 (image upload) and
     the AWS CLI (backup script).
3. **Pages projects** (connect the GitHub repo, or direct upload of `dist/`):
   - Admin: build `apps/admin`, output `dist/`, build env
     `VITE_API_BASE_URL=https://api-staging.cinematiccelebration.in`.
   - Web: build `apps/web`, output `dist/`, build env
     `PUBLIC_API_BASE_URL=https://api-staging.cinematiccelebration.in`.
   - Note each project's assigned `*.pages.dev` URL — these are the trial URLs.
4. Set the API `CORS_ALLOWED_ORIGINS` to exactly those two `*.pages.dev` origins.

---

## Phase D — Production .env (Req 4)

Copy `.env.example` → `New_Application/.env` on the VPS and fill:

| Var | Trial value |
|---|---|
| `ENVIRONMENT` | `staging` |
| `POSTGRES_USER/PASSWORD/DB` | strong random password |
| `DATABASE_URL` | `postgresql+psycopg://<user>:<pw>@postgres:5432/<db>` (driver-qualified) |
| `JWT_SECRET` | 32+ random bytes (`openssl rand -hex 32`) |
| `CORS_ALLOWED_ORIGINS` | the two `*.pages.dev` URLs (comma-separated) |
| `COOKIE_SAMESITE` | `none` (cross-site trial) |
| `COOKIE_SECURE` | `true` |
| `API_HOST` | `api-staging.cinematiccelebration.in` |
| `R2_ENDPOINT_URL` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | from R2 token |
| `R2_PUBLIC_BUCKET` / `R2_PRIVATE_BUCKET` / `IMG_CDN_DOMAIN` | the bucket names + `img.cinematiccelebration.in` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | same R2 token (for backup.sh) |
| `MANUAL_UPI_VPA` | real UPI VPA |
| `PENDING_HOLD_MINUTES` | `120` (or chosen) |
| `SMTP_HOST` / `SMTP_USERNAME` / `SMTP_PASSWORD` | **blank** (email disabled) |

`.env` is git-ignored (confirmed) and never committed.

**Cookie rationale.** Trial: admin `*.pages.dev` and API `api-staging.` are
different registrable domains → cookie must be `SameSite=None; Secure`. After
cutover both are under `cinematiccelebration.in` → `SameSite=Lax`.

**Email.** `app/integrations/email.py` already no-ops when `SMTP_HOST` is blank
(logs `email_skipped_no_smtp`, returns) and swallows any send error, so booking
creation never fails on email. No code change required.

---

## Phase E — First deploy (Req 5)

On a **1 GB** box, build the image OFF the VPS (see Phase A guardrail) and pull it,
rather than `docker compose build` on the box. Preferred flow:
```bash
# Elsewhere (Codespace/CI): build and push the api image to a registry (e.g. GHCR)
#   docker build -t ghcr.io/<org>/cineceleb-api:latest apps/api && docker push ...
# On the VPS, from New_Application/deploy, as the deploy user:
docker compose pull                                 # fetch the prebuilt api image
docker compose run --rm api alembic upgrade head   # MUST succeed before workers
docker compose up -d                                # postgres + api + caddy
curl https://api-staging.cinematiccelebration.in/healthz
```
(If you ever build on the box, stop api+postgres first to avoid an OOM kill.)
If `alembic upgrade head` fails, stop — do not start workers.

> This implies `docker-compose.yml` should reference an `image:` (registry) for
> the api service for pull-based deploys, keeping `build:` as a fallback. A task
> covers wiring this; it does not change application code.

---

## Phase F — Seed minimal data (Req 6)

Enough to log in and smoke-test; NOT the real data import (separate later spec).
Use a one-off script/CLI run inside the api container to create:
- one admin user (password argon2-hashed via `app.core.security.hash_password`),
- the 3 branch locations,
- a minimal catalog: ≥1 plan with availability so a public booking can be made.

> A seed entrypoint will be identified/added in tasks (e.g. a small
> `python -m app.jobs.seed_min` or a documented `psql`/script). The admin
> password is supplied at seed time, never committed.

---

## Phase G — Scheduled jobs (Req 7)

```bash
mkdir -p /var/log/cc
chmod +x deploy/backup/backup.sh
crontab deploy/cron/crontab     # after fixing the repo path inside it
```
- `expire_pending` every minute inside the api container (idempotent).
- Nightly backup at 02:00 IST (20:30 UTC).

---

## Phase H — Backups + tested restore (Req 8)

`backup/backup.sh` already: `pg_dump | gzip` → R2 `backups/daily/<date>.sql.gz`,
and on Sundays also `backups/weekly/`. Retention 14 daily + 8 weekly (enforced by
an R2 lifecycle rule — document it). Required envs (`R2_ENDPOINT_URL`,
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) make it fail loudly if missing.

**Mandatory restore drill:** download the latest dump, restore into a scratch DB
(a throwaway `postgres` container or a scratch database), and verify row counts /
a known record. Record the exact steps in `deploy/backup/RESTORE.md`.

---

## Phase I — Observability & security checklist (Req 9, 10)

- Uptime monitor (e.g. UptimeRobot free) on
  `https://api-staging.cinematiccelebration.in/healthz` (switch to `api.` at cutover).
- `docker stats` to confirm each service stays within its mem_limit.
- Logs: `docker compose logs -f api` — JSON to stdout, no PII beyond booking ref,
  no tokens/secrets.
- Security checklist: HTTPS-only; cookie httpOnly+Secure (`None` trial/`Lax`
  after); CORS explicit (not `*`); no secrets in git or images; admin site
  `noindex`; rate limits active on login + public booking (slowapi, already in code).

---

## Phase J — Trial smoke test & open review (Req 11)

On the `*.pages.dev` URLs:
1. Admin login works.
2. Public booking → `pending` holds the slot.
3. Admin accepts after recording sufficient advance.
4. Time sheet + cake sheet render and export (.xlsx).
5. Analytics load for admin.
6. Image upload succeeds and serves from `img.cinematiccelebration.in`.

Then run the ~1-week open review: collect defects/improvements, fix, redeploy to
staging (API: `git pull` + `docker compose build api` + `alembic upgrade head` +
`up -d`; frontends: Pages rebuild). Legacy stays live and unchanged throughout.
Conclude only on explicit owner sign-off.

---

## Phase K — Cutover + reversible rollback (Req 12)

Pre-step: lower TTL on the apex + `admin.` + `api` records (e.g. 300s) a day
ahead, and **record the legacy DNS values**.

After sign-off, in order, verifying each step:
1. Add `A api → <VPS_IP>`; set `API_HOST=api.cinematiccelebration.in` in `.env`;
   `docker compose up -d` (Caddy gets the new cert); verify `/healthz`.
2. On Cloudflare Pages, attach custom domains: admin →
   `admin.cinematiccelebration.in`, web → apex (+`www`).
3. Rebuild both frontends with `VITE_API_BASE_URL` / `PUBLIC_API_BASE_URL` =
   `https://api.cinematiccelebration.in`. Set `COOKIE_SAMESITE=lax`,
   `ENVIRONMENT=production`, and `CORS_ALLOWED_ORIGINS` to the real origins;
   restart the api.
4. **Last:** repoint the apex `cinematiccelebration.in` and
   `admin.cinematiccelebration.in` away from Hostinger to Cloudflare Pages.
5. Point the uptime monitor at `api.cinematiccelebration.in`.

**Rollback:** if anything fails after cutover, restore the recorded legacy DNS
values for the apex and `admin.` — traffic returns to Hostinger (low TTL makes
this quick). The VPS/Pages trial environment can keep running while you debug.

---

## Changes to the repo this design implies (for tasks)

Small, additive — most of deploy/ is reused as-is:
1. `deploy/Caddyfile`: use `{$API_HOST}` instead of the hardcoded host.
2. `deploy/docker-compose.yml`: pass `API_HOST` env to the caddy service.
3. `.env.example`: add `API_HOST` (+ `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
   if not already present for the backup script) and a comment on trial vs
   production cookie policy.
4. A minimal seed path for the admin user + 3 locations + minimal catalog
   (script or documented commands).
5. `deploy/README.md` + `deploy/backup/RESTORE.md`: expand into this trial→cutover
   runbook and the restore drill.
No application/business-logic code changes; email no-op already satisfies the
"email disabled" requirement.

---

## Testing / verification

This spec is operational, so "tests" are the documented drills, all must pass:
- `/healthz` 200 over HTTPS on staging (and later production).
- Trial smoke test (6 checks above) green on the `*.pages.dev` URLs.
- Backup restore drill succeeds into a scratch DB (recorded in RESTORE.md).
- Security checklist all ticked.
- Existing automated suites (`pytest`, `vitest`) remain green after the small
  Caddyfile/compose/.env.example edits (no app logic touched).
