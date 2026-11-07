# Requirements Document

## Introduction

This spec covers taking the finished Phase 1 Cinematic Celebration application to production for the **first time** on a brand-new environment. Cinematic Celebration is a private theatre booking platform operating 3 branches in Bangalore with tens of bookings per day and a small admin team.

The hosting shape is already decided and matches the existing `New_Application/deploy/` scaffolding (`docker-compose.yml`, `Caddyfile`, `cron/crontab`, `backup/backup.sh`, `README.md`). This spec **builds on** that scaffolding; it does not recreate it.

- **API stack:** one small Linux VPS (recommended Hetzner CX22 ~€4/mo, or a DigitalOcean $6 droplet) running Docker Compose — FastAPI/uvicorn (2 workers) + PostgreSQL 16 + Caddy (automatic HTTPS).
- **Frontends:** the admin panel (React/Vite) and the customer site (Astro) are static builds hosted on Cloudflare Pages (free tier).
- **Object storage:** public images and private nightly DB backups on Cloudflare R2 (S3-compatible, via boto3 / AWS CLI).
- **Domain:** `cinematiccelebration.in` is already registered and **the legacy system is LIVE and in active use**: the customer site at the apex `cinematiccelebration.in` and the admin panel at `admin.cinematiccelebration.in` (Node + MariaDB on Hostinger). These production hostnames MUST NOT be touched during this spec.
- **Trial-first rollout (explicit owner decision):** the new system is deployed to **temporary staging URLs** and run in parallel with the live legacy site for a **~1-week trial** (open review for defects/improvements) BEFORE any real domain is linked. During the trial: the API uses the temporary subdomain `api-staging.cinematiccelebration.in` (a new, unused subdomain — a harmless A record that does not affect the live apex or `admin.` subdomain), and the two frontends use their free Cloudflare Pages `*.pages.dev` URLs. Only after the trial is signed off are the real custom domains (`api.cinematiccelebration.in`, `admin.cinematiccelebration.in`, and the apex customer site) linked — the final, reversible cutover.

Total infrastructure cost must stay under $7/month, within a 1–2 GB RAM VPS class, honouring the memory limits already set in `docker-compose.yml` (postgres 300m, api 220m, caddy 40m).

Because this spec touches secrets, access control, and money-adjacent configuration, it includes an explicit verification checklist (smoke tests, security checks, and a backup restore drill) as required by the steering rules.

### Known starting conditions

- The user **has** the domain `cinematiccelebration.in`.
- The user does **not** yet have: a VPS, a Cloudflare account, or SMTP email credentials.
- **Email is intentionally out of scope for this phase.** Booking confirmation email is optional and must be fully disabled when SMTP is not configured. A later WhatsApp-notifications spec will replace email entirely.

## Glossary

- **VPS**: The single small Linux virtual private server (1–2 GB RAM) that runs the Docker Compose stack.
- **Stack**: The Docker Compose services on the VPS — API, PostgreSQL, and Caddy — as defined in `deploy/docker-compose.yml`.
- **API**: The FastAPI application served by uvicorn (2 workers) behind Caddy. During the trial it is reachable at `https://api-staging.cinematiccelebration.in`; after cutover, at `https://api.cinematiccelebration.in`.
- **Caddy**: The reverse proxy on the VPS that terminates TLS and provides automatic HTTPS.
- **Deployer**: The human operator (the user) performing provisioning, deployment, and go-live steps.
- **Trial_Period**: The ~1-week window during which the new system runs on temporary staging URLs in parallel with the live Legacy_System, for open review of defects and improvements, before any real domain is linked.
- **Staging_URLs**: The temporary hostnames used during the Trial_Period — `api-staging.cinematiccelebration.in` for the API and the free Cloudflare Pages `*.pages.dev` URLs for the Admin_Site and Customer_Site.
- **Deploy_User**: The non-root Linux user on the VPS used to run Docker Compose and deployment commands.
- **Cloudflare_Pages**: The static hosting platform serving the admin panel and customer site builds.
- **R2**: Cloudflare R2 object storage (S3-compatible). Includes a public images bucket and a private backups bucket.
- **Admin_Site**: The React/Vite admin panel static build (served at `admin.cinematiccelebration.in`).
- **Customer_Site**: The Astro customer site static build (served at the apex `cinematiccelebration.in` and/or `www`).
- **Legacy_System**: The existing live Node + MariaDB application hosted on Hostinger at `cinematiccelebration.in`.
- **Backup_Job**: The nightly `deploy/backup/backup.sh` job that performs `pg_dump`, gzips, and uploads to the private R2 bucket.
- **Expire_Job**: The scheduled `python -m app.jobs.expire_pending` job run every minute to expire unpaid pending bookings.
- **Env_File**: The production `New_Application/.env` file, filled from the committed `.env.example`, never committed to git.
- **Healthz**: The `GET /healthz` endpoint used for uptime monitoring, returning `{"status":"ok"}`.
- **DNS_Cutover**: The deliberate, reversible step of repointing the apex domain away from the Legacy_System to Cloudflare_Pages.

## Requirements

### Requirement 1: Provision the VPS

**User Story:** As the Deployer, I want a provider-agnostic VPS baseline with Docker, a firewall, and a non-root user, so that the Stack runs on a secure, minimal host within budget.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document provisioning a single Linux VPS with 1–2 GB RAM, using Hetzner CX22 as the worked example and noting DigitalOcean's $6 droplet as an equivalent alternative.
2. WHERE the VPS is provisioned, THE production-deployment runbook SHALL specify a current long-term-support Linux distribution as the OS baseline.
3. THE production-deployment runbook SHALL document installing Docker Engine and the Docker Compose plugin on the VPS.
4. THE production-deployment runbook SHALL document creating a non-root Deploy_User with permission to run Docker, and SHALL document that routine deployment commands run as the Deploy_User rather than root.
5. THE production-deployment runbook SHALL document configuring a host firewall that allows inbound TCP ports 80 and 443 and the SSH port, and denies other inbound ports by default.
6. WHERE SSH access is configured, THE production-deployment runbook SHALL document using key-based authentication for the Deploy_User.
7. THE production-deployment runbook SHALL confirm that the Stack's configured memory limits (postgres 300m, api 220m, caddy 40m) fit within the chosen VPS RAM class, keeping total monthly infrastructure cost under $7.

### Requirement 2: Configure DNS and HTTPS for the API (staging first)

**User Story:** As the Deployer, I want the API reachable over automatic HTTPS on a temporary staging subdomain during the trial, so that I can test the new system without touching the live Legacy_System's hostnames.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document creating a DNS A record for the staging subdomain `api-staging.cinematiccelebration.in` pointing to the VPS public IP address, and SHALL confirm this record does not affect the live apex `cinematiccelebration.in` or `admin.cinematiccelebration.in`.
2. WHILE the staging API DNS record and firewall are in place, THE Caddy SHALL obtain and serve a valid TLS certificate for `api-staging.cinematiccelebration.in` (the existing `Caddyfile` host is updated to the staging hostname for the Trial_Period).
3. THROUGHOUT the Trial_Period, THE production-deployment runbook SHALL keep the Legacy_System reachable and unchanged at both `cinematiccelebration.in` and `admin.cinematiccelebration.in`.
4. WHEN the Deployer requests `https://api-staging.cinematiccelebration.in/healthz`, THE API SHALL return HTTP 200 with body `{"status":"ok"}`.
5. THE production-deployment runbook SHALL document that the API is reachable only over HTTPS and that plain HTTP requests are redirected to HTTPS by Caddy.
6. WHERE the trial is signed off (see Requirement 11), THE production-deployment runbook SHALL document switching the Caddy host and DNS to the final `api.cinematiccelebration.in` as a later, reversible step.

### Requirement 3: Set up Cloudflare account, R2 buckets, and Pages projects

**User Story:** As the Deployer, I want a Cloudflare account with R2 buckets and Pages projects wired to the real origins, so that images, backups, and the static frontends are hosted for free and correctly connected to the API.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document creating a Cloudflare account and adding the `cinematiccelebration.in` zone.
2. THE production-deployment runbook SHALL document creating a public R2 bucket for images, served from the `IMG_CDN_DOMAIN` (`img.cinematiccelebration.in`) CDN domain.
3. THE production-deployment runbook SHALL document creating a private R2 bucket for backups that is not publicly readable.
4. THE production-deployment runbook SHALL document creating a Cloudflare_Pages project for the Admin_Site built from `apps/admin` and a Cloudflare_Pages project for the Customer_Site built from `apps/web`.
5. DURING the Trial_Period, THE Admin_Site and Customer_Site SHALL be reachable at their free Cloudflare Pages `*.pages.dev` URLs, and NO custom domain SHALL be attached to either project.
6. DURING the Trial_Period, THE Admin_Site build-time `VITE_API_BASE_URL` and the Customer_Site build-time `PUBLIC_API_BASE_URL` SHALL be set to `https://api-staging.cinematiccelebration.in`.
7. DURING the Trial_Period, THE API `CORS_ALLOWED_ORIGINS` SHALL list exactly the two `*.pages.dev` origins (Admin_Site and Customer_Site) and SHALL NOT use a wildcard.
8. WHERE the trial is signed off (see Requirement 11), THE production-deployment runbook SHALL document the cutover: attaching the custom domains (Admin_Site at `admin.cinematiccelebration.in`, Customer_Site at the apex and/or `www`), rebuilding both frontends with the API base URL set to `https://api.cinematiccelebration.in`, and updating `CORS_ALLOWED_ORIGINS` to the real origins.
9. THE production-deployment runbook SHALL document creating the public image CDN hostname `img.cinematiccelebration.in` as a harmless new subdomain that does not affect the live apex or `admin.` subdomain.

### Requirement 4: Fill the production environment file

**User Story:** As the Deployer, I want the production Env_File filled from `.env.example` with real secrets and production-safe policies, so that the Stack runs securely with no secrets in git.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document copying `.env.example` to `New_Application/.env` and populating every variable required by the Stack.
2. THE Env_File SHALL contain strong, randomly generated values for `POSTGRES_PASSWORD`, the matching `DATABASE_URL`, and `JWT_SECRET`.
3. THE Env_File SHALL set `CORS_ALLOWED_ORIGINS` to the explicit Admin_Site and Customer_Site origins (the `*.pages.dev` URLs during the Trial_Period) and SHALL NOT use a wildcard value.
4. DURING the Trial_Period, because the Admin_Site (`*.pages.dev`) and the API (`api-staging.cinematiccelebration.in`) are on different registrable domains, THE Env_File SHALL set the auth cookie policy to httpOnly, `Secure`, and `SameSite=None` so the login cookie is sent on cross-site requests.
4a. AFTER cutover, because the Admin_Site (`admin.cinematiccelebration.in`) and the API (`api.cinematiccelebration.in`) share the registrable domain `cinematiccelebration.in`, THE Env_File SHALL set the auth cookie policy to httpOnly, `Secure`, and `SameSite=Lax`.
5. THE Env_File SHALL contain the R2 credentials, bucket names, endpoint URL, and `IMG_CDN_DOMAIN` needed by image upload and the Backup_Job.
6. THE Env_File SHALL set `MANUAL_UPI_VPA` to the real UPI VPA for manual advance payment instructions.
7. THE Env_File SHALL set `PENDING_HOLD_MINUTES` to the intended production hold duration.
8. THE Env_File SHALL leave the `SMTP_HOST`, `SMTP_USERNAME`, and `SMTP_PASSWORD` values blank so that email remains disabled.
9. THE production-deployment runbook SHALL confirm that `New_Application/.env` is excluded from git and is never committed.

### Requirement 5: Execute the first deploy sequence

**User Story:** As the Deployer, I want a first-deploy sequence that migrates the database to completion before any worker starts, so that no worker ever serves against an old schema.

#### Acceptance Criteria

1. WHEN the first deploy begins, THE Deployer SHALL build the API image with `docker compose build api`.
2. WHEN the API image is built, THE Deployer SHALL run `alembic upgrade head` to completion before starting the API workers.
3. IF `alembic upgrade head` fails, THEN THE Deployer SHALL halt the deploy and SHALL NOT start the API workers until migrations succeed.
4. WHEN migrations have completed successfully, THE Deployer SHALL start the full Stack with `docker compose up -d`.
5. WHEN the Stack is running, THE Deployer SHALL verify `https://api-staging.cinematiccelebration.in/healthz` returns HTTP 200 with `{"status":"ok"}`.

### Requirement 6: Seed the minimal initial data

**User Story:** As the Deployer, I want a minimal initial admin user and the 3 locations with a minimal catalog seeded, so that staff can log in and the environment can be smoke-tested before real data import.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document seeding exactly one initial admin user with a credential set by the Deployer at seed time.
2. THE production-deployment runbook SHALL document seeding the 3 Bangalore branch locations.
3. THE production-deployment runbook SHALL document seeding a minimal catalog sufficient to create a test booking (at least one bookable plan and the availability needed for a public booking).
4. WHEN the admin user is seeded, THE API SHALL store the password as an argon2 hash and SHALL NOT store it in plain text.
5. THE production-deployment runbook SHALL state that this seed is the minimum needed to operate and smoke-test, and that importing real production data is handled by a separate later spec.

### Requirement 7: Install scheduled jobs

**User Story:** As the Deployer, I want the host crontab installed for the Expire_Job and Backup_Job, so that pending bookings expire and backups run automatically.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document creating the `/var/log/cc` log directory on the VPS.
2. THE production-deployment runbook SHALL document installing the host crontab from `deploy/cron/crontab` after adjusting the repository path.
3. WHILE the crontab is installed, THE Expire_Job SHALL run every minute inside the API container and SHALL be idempotent.
4. WHILE the crontab is installed, THE Backup_Job SHALL run nightly at the scheduled time.
5. THE production-deployment runbook SHALL document making `deploy/backup/backup.sh` executable.

### Requirement 8: Nightly backups and a tested restore

**User Story:** As the Deployer, I want nightly database backups to R2 with retention and at least one proven restore, so that data loss is recoverable.

#### Acceptance Criteria

1. WHEN the Backup_Job runs, THE Backup_Job SHALL produce a gzipped `pg_dump` of the production database and upload it to the private R2 backups bucket under a daily path.
2. WHILE the current day is the configured weekly day, THE Backup_Job SHALL additionally upload the dump to a weekly path.
3. THE backup retention policy SHALL keep 14 daily backups and 8 weekly backups.
4. THE production-deployment runbook SHALL document performing at least one test restore of a backup into a scratch database and verifying the restored data.
5. IF a required backup environment variable (such as `R2_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, or `AWS_SECRET_ACCESS_KEY`) is missing, THEN THE Backup_Job SHALL fail with a clear error and SHALL NOT upload an incomplete backup.
6. THE production-deployment runbook SHALL record the restore procedure in `deploy/backup/RESTORE.md`.

### Requirement 9: Observability and operational fit

**User Story:** As the Deployer, I want uptime monitoring, confirmed memory fit, and safe structured logs, so that the Stack is observable and stays within budget without leaking sensitive data.

#### Acceptance Criteria

1. THE production-deployment runbook SHALL document configuring an external uptime monitor against `https://api.cinematiccelebration.in/healthz`.
2. WHILE the Stack is running, THE API, PostgreSQL, and Caddy SHALL each operate within their configured memory limits (api 220m, postgres 300m, caddy 40m).
3. WHILE the Stack is running, THE API SHALL emit logs to stdout in JSON format.
4. THE API SHALL NOT write personally identifiable information beyond a booking reference, and SHALL NOT write tokens or secrets, to its logs.
5. THE production-deployment runbook SHALL document how to view and follow the Stack logs on the VPS.

### Requirement 10: Security hardening checklist for go-live

**User Story:** As the Deployer, I want a security hardening checklist completed before go-live, so that the production environment avoids the known flaws of the legacy system.

#### Acceptance Criteria

1. THE go-live checklist SHALL verify that all API and site traffic is served over HTTPS only.
2. THE go-live checklist SHALL verify that the auth cookie is httpOnly and `Secure`, with `SameSite=None` during the Trial_Period and `SameSite=Lax` after cutover.
3. THE go-live checklist SHALL verify that `CORS_ALLOWED_ORIGINS` is an explicit allowlist and is not `*`.
4. THE go-live checklist SHALL verify that no secrets are present in git history or in the deployed images.
5. THE go-live checklist SHALL verify that the Admin_Site responds with a `noindex` directive so it is not indexed by search engines.
6. THE go-live checklist SHALL verify that rate limiting is active on the login endpoint and on public booking creation.

### Requirement 11: Trial-period smoke test and open review

**User Story:** As the Deployer, I want to smoke-test the new system on the Staging_URLs and run an open ~1-week review while the Legacy_System stays live, so that defects and improvements are caught before any real domain is linked.

#### Acceptance Criteria

1. THE trial smoke test SHALL verify that an admin can log in to the Admin_Site on its `*.pages.dev` URL.
2. THE trial smoke test SHALL verify that creating a public booking on the Customer_Site `*.pages.dev` URL produces a `pending` booking that holds the slot.
3. THE trial smoke test SHALL verify that an admin can accept a `pending` booking after recording a sufficient advance.
4. THE trial smoke test SHALL verify that the time sheet and cake sheet render and export for the booked slot.
5. THE trial smoke test SHALL verify that analytics load for an admin.
6. THE trial smoke test SHALL verify that an image upload succeeds and is served from the public R2 CDN domain.
7. THROUGHOUT the Trial_Period, THE Legacy_System SHALL remain live and unchanged at `cinematiccelebration.in` and `admin.cinematiccelebration.in`.
8. DURING the Trial_Period, THE Deployer SHALL collect defects and improvement requests through open review, and these SHALL be addressed and redeployed to the Staging_URLs before sign-off.
9. THE Trial_Period SHALL be concluded only by an explicit sign-off from the Deployer that the new system is ready.

### Requirement 12: Cutover to the real domain and reversible rollback

**User Story:** As the Deployer, I want the real domain linked only after trial sign-off, and a documented reversible rollback, so that the switch is safe and the Legacy_System remains a fallback.

#### Acceptance Criteria

1. WHEN trial sign-off is given, THE Deployer SHALL switch the API to `api.cinematiccelebration.in` (update DNS + the Caddy host) and confirm Caddy serves a valid certificate and `/healthz` returns 200.
2. WHEN trial sign-off is given, THE Deployer SHALL attach the Admin_Site custom domain `admin.cinematiccelebration.in` and the Customer_Site custom domain (apex and/or `www`) on Cloudflare_Pages.
3. WHEN the frontends are moved to custom domains, THE Deployer SHALL rebuild both with the API base URL set to `https://api.cinematiccelebration.in`, set the auth cookie policy to `SameSite=Lax`, and update `CORS_ALLOWED_ORIGINS` to the real origins.
4. THE cutover SHALL repoint the apex `cinematiccelebration.in` and `admin.cinematiccelebration.in` away from the Legacy_System to the new system as the final step, after all other changes are verified.
5. BEFORE the apex cutover, THE Deployer SHALL note the Legacy_System's current DNS values so they can be restored.
6. IF the new environment fails verification after cutover, THEN THE Deployer SHALL revert DNS for the apex and `admin.` back to the Legacy_System using the recorded values (reversible rollback).
7. THE production-deployment runbook SHALL note that DNS TTLs should be lowered ahead of cutover so a rollback propagates quickly.

## Non-Goals

The following are explicitly **out of scope** for this spec and will be handled separately:

- **Real data migration (MariaDB → PostgreSQL):** importing the Legacy_System's production data is a separate spec that will run **after** this environment is live. A `scripts/migrate_from_mariadb/` migrator already exists but is not exercised here; this spec seeds only the minimal data needed to operate and smoke-test.
- **PhonePe / payment gateway:** Phase 1 uses manual advance recorded by staff. Any payment gateway integration is a later spec.
- **WhatsApp / automated notifications:** a future WhatsApp-notifications spec will handle customer notifications and will replace email. No WhatsApp design is included here.
- **Email confirmations:** booking confirmation email is disabled this phase. With blank `SMTP_*` values, the API must send no email, and the absence of SMTP configuration must not error or block booking creation or go-live.
- **CI/CD automation:** manual deployment is acceptable for Phase 1. Automated build/deploy pipelines are out of scope unless a step is trivially scriptable within the existing runbook.
