# Cinematic Celebration — New Application (Phase 1)

Rebuild of the Cinematic Celebration private-theater booking platform.

Phase 1 has **no online payment gateway**: customer bookings are *requests* that hold a slot in
`pending` state; staff record the advance (cash/UPI/card) in a payments ledger and accept or reject
the booking in the admin panel. A real gateway (likely Cashfree) is deferred to a later phase behind
the `PaymentProvider` interface (`ManualProvider` only in Phase 1).

See `.kiro/specs/cinematic-celebration-system/` for requirements, design, and the task plan, and
`.kiro/steering/` for the tech stack and project conventions.

## Structure

```
New_Application/
├── apps/
│   ├── api/        # FastAPI backend (Python 3.12, SQLAlchemy 2.0, PostgreSQL 16)
│   ├── admin/      # React 18 + TypeScript admin panel (Vite, static build)
│   └── web/        # Astro customer site (static output + React islands)
├── deploy/         # docker-compose, Caddyfile, cron, backup scripts
├── scripts/        # migrate_from_mariadb (one-off data migration)
└── docs/           # architecture notes, runbooks, API notes
```

## Prerequisites

- Python 3.12 (specifically — not 3.13+)
- Node.js 20 LTS (or 18 LTS) + npm
- Docker + Docker Compose (provides PostgreSQL; no separate Postgres install needed)
- Git

See **`docs/PREREQUISITES.md`** for exact versions, Windows (winget) install
commands, download links, and how to verify each tool. Then follow
**`docs/VERIFICATION.md`** to install dependencies and run every app + the
Docker Compose stack.
