#!/usr/bin/env bash
# One-time setup when the Codespace / dev container is created.
# Installs backend + both frontend dependency sets so everything is ready.
set -e

echo "=== Backend (apps/api) ==="
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
# Seed a local .env if missing (edit DATABASE_URL to your Neon string).
[ -f .env ] || cp .env.example .env
deactivate
cd ../..

echo "=== Admin panel (apps/admin) ==="
cd apps/admin
npm install
[ -f .env ] || cp .env.example .env
cd ../..

echo "=== Customer site (apps/web) ==="
cd apps/web
npm install
[ -f .env ] || cp .env.example .env
cd ../..

echo "=== Wiring .env URLs (Codespace-aware) ==="
bash .devcontainer/wire-env.sh || true

echo ""
echo "Setup complete."
echo "Next:"
echo "  1. Put your Neon connection string in apps/api/.env (DATABASE_URL=...)."
echo "     Keep the CORS_ALLOWED_ORIGINS line that wire-env.sh set."
echo "  2. Backend:  cd apps/api && . .venv/bin/activate && alembic upgrade head && uvicorn app.main:app --reload --port 8000"
echo "  3. Admin:    cd apps/admin && npm run gen:api && npm run dev"
echo "  4. Web:      cd apps/web && npm run dev"
echo "  5. In the Ports tab, set port 8000 visibility to PUBLIC so the browser"
echo "     frontends can call the API."
