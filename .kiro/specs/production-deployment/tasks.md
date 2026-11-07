# Implementation Plan — Production Deployment (trial-first)

Two kinds of tasks:
- **[code]** repo/scaffolding edits done in this workspace (committed, verified).
- **[ops]** provisioning/runbook steps the Deployer performs on the providers
  (Hetzner/Cloudflare/DNS), guided by the runbook. Marked `*` (manual, not
  code-completable here) so they don't block the automated suite.

---

- [x] 1. [code] Parameterise Caddy host + pull-based api image
  - Edit `deploy/Caddyfile` to use `{$API_HOST}` instead of the hardcoded
    `api.cinematiccelebration.in`.
  - Edit `deploy/docker-compose.yml` to pass `API_HOST` env to the `caddy`
    service, and add an `image:` (registry, e.g. GHCR) to the `api` service for
    pull-based deploys while keeping `build:` as a fallback (1 GB box builds
    off-box — see design Phase A/E guardrail).
  - Add `API_HOST` to `.env.example` with a comment (staging vs production).
  - _Requirements: 2, 5, 12_

- [x] 2. [code] Env template + backup credentials
  - Ensure `.env.example` documents every variable the runbook uses:
    `API_HOST`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for `backup.sh`),
    and a comment block on the trial (`SameSite=None`) vs production
    (`SameSite=Lax`) cookie policy.
  - Confirm `.env` is git-ignored (no change expected; verify).
  - _Requirements: 4, 8_

- [x] 3. [code] Minimal seed path (admin + locations + minimal catalog)
  - [x] 3.1 Add a small, idempotent seed CLI, e.g. `python -m app.jobs.seed_min`,
    that creates one admin user (password from an env/arg, argon2-hashed via
    `app.core.security.hash_password`), the 3 branch locations, and a minimal
    bookable catalog (≥1 plan + availability) sufficient for a public booking.
    It MUST NOT insert if the data already exists (idempotent) and MUST NOT
    contain any hardcoded password.
    - _Requirements: 6_
  - [x] 3.2 Add a focused test that seeding is idempotent and that the admin
    password is stored as an argon2 hash (never plain text).
    - _Requirements: 6_

- [x] 4. [code] Expand the deployment docs into the trial→cutover runbook
  - Rewrite/extend `deploy/README.md` to the phased runbook (provision → DNS
    staging → Cloudflare/R2/Pages → .env → first deploy → seed → cron → backups
    → smoke test → ~1-week review → cutover → rollback).
  - Expand `deploy/backup/RESTORE.md` with the exact restore-drill steps
    (download latest dump → restore into a scratch DB → verify counts/record).
  - _Requirements: 1, 2, 3, 5, 6, 7, 8, 11, 12_

- [ ] 5. [code] Verify the small edits don't break anything
  - Run `pytest` (API) and `vitest` (admin + web) — no app logic changed, so
    they must stay green. Run `ruff`/`eslint`. Confirm `docker compose config`
    parses with the new `API_HOST` wiring.
  - _Requirements: 5_

- [ ] 6. [ops]* Provision the VPS (cheap 1 GB India VPS)
  - Create a cheap, reliable 1 GB India-region VPS (CloudPe ~₹350/mo, or Vultr
    Bangalore / DO BLR1 ~₹450-550/mo), Ubuntu 24.04 LTS, x86_64, annual prepay.
    SSH key auth; non-root `deploy` user with Docker rights; ufw allow
    SSH/80/443; disable SSH password + root login; clone the repo under
    `/opt/cinematic`.
  - **1 GB guardrails:** add a 1 GB swap file (`/swapfile`, in `/etc/fstab`); plan
    to build the api image OFF the box and `docker compose pull` (do NOT
    `build` on the box). Do NOT use Oracle for production.
  - _Requirements: 1_

- [ ] 7. [ops]* DNS + HTTPS for the staging API
  - Add `A api-staging → <VPS_IP>`; set `API_HOST=api-staging.cinematiccelebration.in`
    in `.env`; confirm Caddy issues a cert and `/healthz` is 200 over HTTPS.
    Leave the live apex and `admin.` records untouched.
  - _Requirements: 2_

- [ ] 8. [ops]* Cloudflare account, R2 buckets, Pages projects
  - Create account + add the zone (keep legacy DNS intact); create public images
    bucket (+ `img.` CDN domain) and private backups bucket; create an R2 API
    token; create the two Pages projects building `apps/admin` and `apps/web`
    with build-time API URL = the staging API; note the `*.pages.dev` URLs.
  - _Requirements: 3_

- [ ] 9. [ops]* Fill production .env + first deploy + seed
  - Fill `.env` per the design table (staging values; SMTP blank; cookies
    `None`+`Secure`; CORS = the two `*.pages.dev` origins). Build the api image
    OFF the box (Codespace/CI → push to registry), then on the VPS:
    `docker compose pull` → `run --rm api alembic upgrade head` (must succeed
    before workers) → `up -d` → verify `/healthz`. Run the minimal seed (task 3)
    with a chosen admin password.
  - _Requirements: 4, 5, 6_

- [ ] 10. [ops]* Scheduled jobs + backups + restore drill
  - `mkdir -p /var/log/cc`; `chmod +x deploy/backup/backup.sh`; fix the repo path
    in `deploy/cron/crontab` and install it. Add the R2 lifecycle rule for
    14-daily/8-weekly retention. Perform ONE restore drill into a scratch DB and
    record it in `RESTORE.md`.
  - _Requirements: 7, 8_

- [ ] 11. [ops]* Observability + security checklist
  - Uptime monitor on the staging `/healthz`; `docker stats` memory-fit check;
    confirm JSON logs with no PII/secrets; tick the security checklist (HTTPS
    only, cookie flags, CORS not `*`, no secrets in git/images, admin `noindex`,
    rate limits on login + public booking).
  - _Requirements: 9, 10_

- [ ] 12. [ops]* Trial smoke test + ~1-week open review
  - Run the 6 smoke checks on the `*.pages.dev` URLs (login; public booking
    holds slot; accept-with-advance; sheets render+export; analytics; image
    upload served from `img.`). Collect defects/improvements, fix + redeploy to
    staging, and conclude on explicit owner sign-off. Legacy stays live.
  - _Requirements: 11_

- [ ] 13. [ops]* Cutover to the real domain + reversible rollback
  - Lower TTLs and record legacy DNS values first. Then: add `A api`, set
    `API_HOST=api.cinematiccelebration.in`, redeploy; attach Pages custom domains
    (admin → `admin.`, web → apex/`www`); rebuild frontends with the production
    API URL; set cookies `SameSite=Lax`, `ENVIRONMENT=production`, CORS = real
    origins; repoint the apex + `admin.` away from Hostinger LAST; move the
    uptime monitor to `api.`. Keep the recorded legacy DNS for rollback.
  - _Requirements: 12_
