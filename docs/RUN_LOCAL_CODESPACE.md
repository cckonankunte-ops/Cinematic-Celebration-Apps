# Run the app in a Codespace (local Postgres + retrofitted data)

This is the quick, repeatable runbook for **starting the three apps** (API,
admin, customer web) in a freshly opened Codespace, using the **local Docker
Postgres** container `cc-pg` that already holds the migrated (retrofitted) data.

> Why local Postgres and not Neon? Neon is unreachable from this Codespace
> (IPv6 "Network is unreachable"). We run a throwaway Postgres container instead.
> Your data lives in that container and survives Codespace stop/restart — you do
> **not** reload it each time.

---

## 0. One terminal for setup, then three for the apps

Each app runs a long-lived dev server, so you need **three terminals** open
(use the `+` in the terminal panel). Do the DB step first in any terminal.

---

## 1. Start the database (data is preserved)

A freshly opened Codespace has the `cc-pg` container **stopped**, not deleted.
Just start it:

```bash
docker start cc-pg
```

Verify it's up and has your data:

```bash
docker exec -i cc-pg psql -U postgres -d cinematic -c "SELECT count(*) FROM bookings;"
```

You should see your booking count (thousands of rows).

### Only if `docker start` fails

If you see `container ... already exists` or the container is wedged, reset the
**container** (this does NOT delete the data volume if it's named; but our
throwaway container stores data inside itself, so treat a reset as a data loss
and be ready to re-import):

```bash
docker rm -f cc-pg
docker run -d --name cc-pg \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=cinematic \
  -p 5432:5432 postgres:16-alpine
```

If you had to recreate the container, re-run migrations + re-import (see
section 6). Otherwise skip that.

---

## 2. Wire the Codespace URLs (CORS + cookies + frontend base URLs)

From the repo root, run the helper once per session (idempotent):

```bash
bash .devcontainer/wire-env.sh
```

This fills `apps/admin/.env`, `apps/web/.env`, and the CORS/cookie settings in
`apps/api/.env` with the Codespace's forwarded URLs. It **preserves** your
`DATABASE_URL` in `apps/api/.env`.

---

## 3. Confirm the API points at the local DB

Open `apps/api/.env` and make sure `DATABASE_URL` is the **local** container,
with the `+psycopg` driver prefix:

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/cinematic
```

> Note the `+psycopg` — the app needs the driver-qualified scheme. If you ever
> `export DATABASE_URL=...` in the shell, it overrides `.env`; keep it the same
> value as above.

---

## 4. Start the API (Terminal 1)

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head          # idempotent; no-op if already at latest
uvicorn app.main:app --reload --port 8000
```

Then open the **Ports** tab and set port **8000** visibility to **Public**
(right-click the port → Port Visibility → Public) so the browser frontends can
call it.

Health check (new terminal): `curl -s http://localhost:8000/healthz`

---

## 5. Start the frontends

**Terminal 2 — Admin panel:**

```bash
cd apps/admin
npm run dev        # serves on 5173
```

**Terminal 3 — Customer web site:**

```bash
cd apps/web
npm run dev        # serves on 4321
```

Open the **Ports** tab and click the globe icon next to 5173 (admin) and 4321
(web) to open each in your browser. 5173 and 4321 can stay Private.

### Optional: regenerate admin API types

If you changed API schemas and rely on generated types, with the API running:

```bash
cd apps/admin
npm run gen:api
```

---

## 5b. Verify (tests + build) — run before pushing

Confirmed script names: admin `lint` = `eslint .`, `test` = `vitest run`,
`build` = `tsc -b && vite build`; API uses `pytest` (real Postgres via
testcontainers, so Docker must be running — `cc-pg` already is).

### API (Python) — run all tests

```bash
cd apps/api
source .venv/bin/activate
pytest
```

To run only the files touched by recent changes:

```bash
cd apps/api
source .venv/bin/activate
pytest tests/unit/test_slots.py \
       tests/integration/test_booking_review.py \
       tests/integration/test_booking_validation.py \
       tests/integration/test_booking_accept.py
```

What these cover:
- `test_slots.py` — staff edit grace window (edit during/after a running slot).
- `test_booking_review.py` — admin Review reinstates expired → pending (slot
  re-check 409, non-expired rejected).
- `test_booking_validation.py` — admin/staff may exceed `max_people_allowed`;
  customer cap still enforced; `people >= 1` floor.

### Admin panel (lint + unit tests + type-check/build)

```bash
cd apps/admin
npm run lint
npm run test
npm run build
```

What this covers: the Review button, the plan Edit form + `useUpdatePlan`, the
wider layout (`max-w-screen-2xl`), and the admin max-people booking (no client
cap). `build` runs `tsc -b` so it catches TypeScript errors in the new form/hook.

### Customer web (only if `apps/web` changed)

The recent booking/catalog changes did NOT touch `apps/web`, so this is usually
a no-op — run it only if you edited the customer site:

```bash
cd apps/web
npm run test
npm run build
```

### One-line "all green" gate before a push

```bash
( cd apps/api && source .venv/bin/activate && pytest ) && \
( cd apps/admin && npm run lint && npm run test && npm run build )
```

If every command exits 0, the recent changes (staff edit grace, admin Review of
expired bookings, wider admin layout, plan editing, admin max-people bypass) are
verified; commit and push.

---

## 6. Only if you recreated the DB: re-import the retrofitted data

Skip this unless section 1's reset was needed. From the repo root, with the API
venv active and `DATABASE_URL` exported to the local container:

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
cd ../..
export NEW_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/cinematic'
python -m scripts.migrate_from_mariadb.dump_to_json scripts/cine_celebration_data.sql ./_data
python -m scripts.migrate_from_mariadb.load
```

Then fix the role mapping (old roles `super admin`/`manager` → app roles
`admin`/`staff`) by repointing users:

```bash
docker exec -i cc-pg psql -U postgres -d cinematic -c \
  "UPDATE users SET role_id=(SELECT id FROM user_roles WHERE name='admin') \
   WHERE role_id IN (SELECT id FROM user_roles WHERE name='super admin');"
docker exec -i cc-pg psql -U postgres -d cinematic -c \
  "UPDATE users SET role_id=(SELECT id FROM user_roles WHERE name='staff') \
   WHERE role_id IN (SELECT id FROM user_roles WHERE name='manager');"
```

Set/reset a login password for an admin user:

```bash
cd apps/api
python -m scripts.set_password sachin_admin 'your-new-password'
```

---

## 7. Daily quick start (data already loaded)

```bash
docker start cc-pg
bash .devcontainer/wire-env.sh

# Terminal 1
cd apps/api && source .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload --port 8000
# (set port 8000 to Public in the Ports tab)

# Terminal 2
cd apps/admin && npm run dev

# Terminal 3
cd apps/web && npm run dev
```

---

## Troubleshooting

- **Admin login fails / CORS error**: re-run `bash .devcontainer/wire-env.sh`,
  confirm port 8000 is **Public**, then restart the API.
- **API starts but shows no data**: `DATABASE_URL` is pointing at the wrong DB.
  Run `echo $DATABASE_URL` and check `apps/api/.env` — both must be
  `...@127.0.0.1:5432/cinematic`.
- **`docker start cc-pg` says already exists and won't start**: `docker rm -f cc-pg`
  then re-run the `docker run` from section 1 (and re-import per section 6).
- **Dates look off by one**: the app clock runs in 2026 and the server computes
  in UTC while the browser is IST — expected in this environment.
