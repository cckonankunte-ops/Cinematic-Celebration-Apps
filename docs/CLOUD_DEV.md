# Cloud development — no local installs needed

You do **not** need Node, npm, Docker, or Postgres on your laptop. Everything
runs in **GitHub Codespaces** (a cloud dev environment in your browser) with a
free **Neon** PostgreSQL database. This works on a locked-down office laptop
because nothing is installed locally — it all runs in the browser / cloud.

## One-time: create a free Neon database

1. Go to https://neon.tech and sign up (free tier, no card).
2. Create a project (region closest to you, e.g. Singapore/Mumbai).
3. Copy the **connection string**. It looks like:
   `postgresql://user:password@ep-xxx.aws.neon.tech/dbname?sslmode=require`
4. Convert it for this app by changing the scheme to `postgresql+psycopg`:
   `postgresql+psycopg://user:password@ep-xxx.aws.neon.tech/dbname?sslmode=require`
   Keep this handy — you'll paste it into `apps/api/.env`.

## One-time: enable Codespaces

Codespaces is on by default for personal GitHub accounts (free 60 core-hours
/month). Nothing to install.

## Each session

1. Open the repo on github.com:
   `https://github.com/cckonankunte-ops/Cinematic-Celebration-Apps`
2. Click the green **Code** button → **Codespaces** tab → **Create codespace
   on main** (first time) or reopen your existing one.
3. Wait ~2 minutes while the dev container builds and `setup.sh` installs all
   dependencies automatically (Python venv + both npm installs).
4. In the Codespace terminal, set your database URL once:
   ```bash
   cd apps/api
   # edit .env and set DATABASE_URL to your Neon string (postgresql+psycopg://...)
   ```
   (Use the editor, or: `nano .env`.)

## Run the apps

Open three terminals (the `+` in the terminal panel):

```bash
# Terminal 1 — API
cd apps/api
. .venv/bin/activate
alembic upgrade head
python -m scripts.export_openapi      # generates openapi.json for the frontends
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Admin panel
cd apps/admin
npm run gen:api                        # types from ../api/openapi.json
npm run dev                            # serves on 5173

# Terminal 3 — Customer site
cd apps/web
npm run dev                            # serves on 4321
```

Codespaces auto-forwards ports 8000 / 5173 / 4321. Open the **Ports** tab and
click the globe icon to view each app in your browser.

**The frontend/API URLs and CORS are wired automatically.** The setup script
runs `.devcontainer/wire-env.sh`, which detects the Codespace's forwarded URLs
and fills them into `apps/admin/.env`, `apps/web/.env`, and the
`CORS_ALLOWED_ORIGINS` + cookie settings in `apps/api/.env`. If you ever rebuild
or the URLs change, just re-run it:

```bash
bash .devcontainer/wire-env.sh
```

**One manual step in the Ports tab:** set port **8000** (API) visibility to
**Public** (right-click the port → Port Visibility → Public) so the browser
frontends can call it. Ports 5173 and 4321 can stay private (you open them in
your own browser).

Because the admin and API live on different `*.app.github.dev` subdomains,
`wire-env.sh` sets the auth cookie to `SameSite=None; Secure` automatically in
Codespaces so admin login works.

## Run the tests

```bash
cd apps/api
. .venv/bin/activate
ruff check .
pytest tests/unit        # fast, no DB
pytest                   # full suite — Docker-in-docker is available in the Codespace
```

```bash
cd apps/admin && npm run test && npm run build
cd apps/web   && npm run test && npm run build
```

## Why this fits your constraints

- Nothing installed on the office laptop — Codespaces runs in the browser.
- Docker/Node/Python are preinstalled in the Codespace (see `.devcontainer/`).
- Neon gives a persistent cloud Postgres with just a connection string.
- All free for development/testing. Pick a paid host only at launch.

## When you're ready to launch (later, not now)

Deploy the same repo to free/cheap managed hosts:
- API → Render or Railway (reads `DATABASE_URL` from Neon)
- Admin + Web → Cloudflare Pages or Vercel (static builds)
- Database → keep Neon, or move to the VPS Postgres from the deploy/ config.
