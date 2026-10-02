# Cinematic Celebration API

FastAPI backend. Python 3.12, SQLAlchemy 2.0 (sync), PostgreSQL 16.

## Setup (on a machine with Python 3.12)

```bash
cd New_Application/apps/api
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then edit values
```

## Run the dev server

```bash
uvicorn app.main:app --reload --port 8000
# Health check: http://localhost:8000/healthz  ->  {"status":"ok"}
# OpenAPI docs: http://localhost:8000/docs
```

## Tests

Integration tests use a real PostgreSQL via testcontainers, so **Docker must be running**.

```bash
ruff check .
pytest                      # unit + integration
pytest tests/unit           # unit only (no Docker needed)
```

## Notes

- Phase 1 has no payment gateway. Bookings are manual requests confirmed by staff.
- All money is integer paise. Pricing is server-authoritative.
- Config comes from environment variables / `.env` (see `.env.example`).
