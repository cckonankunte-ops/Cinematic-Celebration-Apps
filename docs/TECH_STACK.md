# Cinematic Celebration — Tech Stack (Phase 1)

Private theatre booking platform. 3 branches in Bangalore, tens of bookings/day,
small admin team. Deliberately cost-sensitive: simplest option that works.

A monorepo with three deployable apps: a FastAPI backend, a React admin panel,
and an Astro customer site. Money is integer paise; pricing is server-authoritative.

---

## Backend (API)

| Component | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Modern, typed |
| Framework | FastAPI | Async-capable, auto OpenAPI schema, Pydantic-native |
| Validation | Pydantic v2 | Request/response models; server-authoritative |
| Server | uvicorn (2 workers) | ASGI server for FastAPI |
| ORM | SQLAlchemy 2.0 (typed, **sync** sessions) | Mature; sync keeps it simple at this scale |
| DB driver | psycopg 3 | PostgreSQL driver |
| Migrations | Alembic | Versioned schema changes (currently at `0014`) |
| Auth | PyJWT (tokens) + argon2-cffi (password hashing) | Tokens in httpOnly cookies; argon2 for passwords |
| Rate limiting | slowapi | Throttles login + public booking creation |
| Excel export | openpyxl | Server-generated `.xlsx` for time/cake sheets |
| Storage SDK | boto3 | Talks to Cloudflare R2 (S3-compatible) |
| Lint / test | ruff, pytest (+ hypothesis) | Property-based tests for pricing/booking |

## Admin panel (static SPA)

| Component | Choice | Why |
|---|---|---|
| Framework | React 18 + TypeScript | — |
| Build tool | Vite | Fast builds → static `dist/` |
| Styling | Tailwind CSS (+ shadcn/ui) | Component styling |
| Routing | React Router | — |
| Server state | TanStack Query | Caching/fetching; no Redux/global store |
| Forms | react-hook-form + zod | Validation mirrors the API |
| API types | openapi-typescript | Generates TS types from the API OpenAPI schema |
| Test | Vitest | — |

## Customer site (static, SEO-friendly)

| Component | Choice | Why |
|---|---|---|
| Framework | Astro (static output) | Ships minimal JS; good SEO + speed |
| Interactivity | React islands | Only the booking wizard is interactive |
| Styling | Tailwind CSS | — |
| Test | Vitest | — |

## Database

| Component | Choice |
|---|---|
| Engine | PostgreSQL 16 |
| Money | Integer **paise** (never floats); UI converts to rupees for display |
| Integrity | Real foreign keys; partial unique index prevents double-booking |
| Time | `timestamptz` stored in UTC; booking dates are `date` in Asia/Kolkata |

---

## Infrastructure (as designed — validate externally)

| Layer | Choice | Notes / cost |
|---|---|---|
| API host | 1 small Linux VPS, Docker Compose (API + Postgres + Caddy) | **Cheapest reliable 1 GB VPS, India region, rupee billing, annual prepay** (~₹350-500/mo). Only the API+Postgres run here; frontends + images are free on Cloudflare, so this is the ENTIRE hosting bill. Start 1 GB + swap; resize to 2 GB only if demand needs it. mem limits pg 300m / api 220m / caddy 40m |
| Reverse proxy / TLS | Caddy 2 | Automatic HTTPS (Let's Encrypt) |
| Static hosting | Cloudflare Pages | Admin + customer site; **free** |
| Object storage | Cloudflare R2 (S3-compatible) | Public images + private backups; ~$0.015/GB, **no egress fees** |
| Email | SMTP via env (optional) | **Disabled in Phase 1** (blank SMTP = no-op) |
| Payments | Manual advance (Phase 1) | PhonePe gateway deferred to its own spec |
| Backups | nightly `pg_dump` → gzip → R2 | 14 daily + 8 weekly; tested restore |
| Scheduling | host cron | `expire_pending` every minute; nightly backup. No in-process scheduler |
| Source control | GitHub | Repo `cckonankunte-ops/Cinematic-Celebration-Apps`; manual deploy for Phase 1 |

---

## Hard constraints driving these choices

- Total infra target **under $7/month**; VPS in the **1–2 GB RAM** class.
- **Never:** Redis, Celery, RabbitMQ, Kubernetes, microservices, GraphQL, SSR
  frameworks (Next/Nuxt SSR), Spring Boot, or any ORM other than SQLAlchemy.
- HTTPS everywhere; secrets only via env (never in code/git/logs); CORS explicit
  allowlist (never `*`).

---

## Deployment decisions to get a second opinion on

1. **VPS provider — DECIDED:** Vultr Bangalore (or DigitalOcean BLR1), India
   region for low latency. Hetzner dropped (2026 price rises, no India region,
   constrained availability).
2. **VPS size — DECIDED:** start **1 GB** (~$5-6/mo, within budget) with a swap
   file + build-image-off-box; resize to **2 GB** (~$10-12/mo) when real demand
   (busy-day latency / OOM / regular ad bursts) justifies it. Reversible in
   minutes on Vultr/DO.
3. **VPS vs managed** — single VPS chosen (per steering). Managed PaaS
   (Render/Railway/Fly) blows the <$7 cap once a real Postgres is added and adds
   vendors; skipped for Phase 1.
4. **Static + storage** — Cloudflare Pages (free) + R2 (cheap, no egress),
   near-optimal on cost. Optional: proxy the API through Cloudflare (free) to
   hide the VPS origin IP.

**Key filter for any suggested host:** the stack is **Docker + Python +
PostgreSQL**. The host must run Docker containers (or at least long-running
Python + a real Postgres). Shared cPanel-style hosting will NOT work — a VPS or a
container platform is required.

---

## Rollout model (trial-first)

1. Deploy to temporary staging URLs: API on `api-staging.cinematiccelebration.in`,
   frontends on free Cloudflare `*.pages.dev` URLs.
2. Run ~1 week in parallel with the live legacy site (untouched) for open review
   of defects/improvements.
3. After sign-off: link real domains (`api.`, `admin.`, apex), fresh data import,
   repoint DNS last — reversible rollback to the legacy site if needed.

Out of scope for Phase-1 deployment (each its own later spec): real MariaDB →
PostgreSQL data migration, PhonePe payments, WhatsApp notifications, email
confirmations, CI/CD automation, multi-tenant SaaS.
