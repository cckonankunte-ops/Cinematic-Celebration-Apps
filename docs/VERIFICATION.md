# Verification Checklist (run on a machine with Python 3.12, Node LTS, Docker)

All code is written and passes static analysis. The commands below are the
"everything green" gate (task 23). They were NOT run on the authoring machine
(no Python 3.12 / Node / Docker there), so run them on your secondary laptop.

## 1. Backend — API (`New_Application/apps/api`)

```bash
cd New_Application/apps/api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Lint
ruff check .

# Migrations round-trip (needs Docker for a throwaway Postgres, or a local PG)
# Point DATABASE_URL at a scratch DB first, then:
alembic upgrade head
alembic downgrade base
alembic upgrade head

# Tests — Docker MUST be running (integration tests use testcontainers Postgres)
pytest                 # unit + integration + all 12 property tests
# unit only (no Docker):
pytest tests/unit

# Export the OpenAPI contract for the frontends
python -m scripts.export_openapi          # writes openapi.json
```

Mandatory test cases to confirm pass: concurrent slot booking, server-side
pricing, booking-request validation, ledger invariant, audit completeness,
accept-requires-advance, pending expiry, role/location access control.

## 2. Admin panel (`New_Application/apps/admin`)

```bash
cd New_Application/apps/admin
npm install
npm run gen:api        # regenerates src/api/schema.ts from ../api/openapi.json
npm run lint
npm run test           # vitest (money, whatsapp, booking-schema, smoke tests)
npm run build          # tsc -b && vite build
```

## 3. Customer site (`New_Application/apps/web`)

```bash
cd New_Application/apps/web
npm install
npm run test           # vitest (formatters, booking islands)
npm run build          # astro build -> dist/
```

## 4. Deployment smoke (`New_Application/deploy`)

```bash
cp ../.env.example ../.env   # then edit real values
cd New_Application/deploy
docker compose build api
docker compose run --rm api alembic upgrade head
docker compose up -d
curl https://localhost/healthz        # or the mapped host; expect {"status":"ok"}
```

## 5. Data migration (only at cutover) — `New_Application/scripts/migrate_from_mariadb`

```bash
cd New_Application/scripts/migrate_from_mariadb
pip install -r requirements.txt
python -m tests  (or) pytest tests/        # pure transform unit tests
python precheck.py       # resolve duplicates + cakeid=1 BEFORE loading
python extract.py && python upload_images.py && python load.py && python validate.py
```

## Definition of Done (per steering)

`ruff`, `pytest`, `eslint`, and `vitest` all clean; a migration exists for every
schema change; new endpoints authenticated/validated; `.env.example` + docs
current. Everything is in place pending the live runs above.
