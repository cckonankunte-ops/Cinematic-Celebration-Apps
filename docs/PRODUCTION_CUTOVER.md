# Production Cutover Runbook — Data Migration + DNS

A complete, newbie-friendly, copy-paste runbook to take the new Cinematic
Celebration app live: pull the latest code, wipe and reload the database from a
fresh legacy dump, re-upload catalog images, then move DNS so the real domain
serves the new app.

> **Audience:** you, running this yourself. Every command is shown. Where a step
> happens in a web dashboard (DigitalOcean / Cloudflare / Hostinger), the clicks
> are spelled out.

---

## 0. The map — who hosts what (read this first)

Three different companies, three different jobs. Nothing here changes which
company you *pay* — moving DNS is free.

| Company | Its job | Cost | Touched in this runbook |
|---|---|---|---|
| **Hostinger** | Registered the domain name `cinematiccelebration.in`; also hosts the OLD live site | Domain renewal (yearly) + old hosting | Only at the very end (change 2 nameservers) |
| **DigitalOcean** | The 1 GB droplet running the NEW API + Postgres + Caddy | $6/month | DB migration runs here |
| **Cloudflare** | DNS management (free) + Pages (the 2 static sites, free) + R2 (images/backups, cents) | Free for DNS + Pages | Attach the real domain here, at the end |

Current new-app addresses (staging):
- API (droplet): `142.93.208.192` → `https://142.93.208.192.sslip.io`
- Customer site (Cloudflare Pages): `cineceleb-web.pages.dev`
- Admin panel (Cloudflare Pages): `cineceleb-admin.pages.dev`

Target production addresses (after DNS):
- API → `api.cinematiccelebration.in`
- Admin → `admin.cinematiccelebration.in`
- Customer → `cinematiccelebration.in` (+ `www`)

**Golden rule:** the old live site stays up and untouched until the final DNS
step. Everything before that happens on the staging URLs.

---

## 1. Prerequisites

- SSH access to the droplet as the `deploy` user.
- The fresh legacy dump committed to the repo at
  `New_Application/scripts/cine_celebration_data.sql` and pushed to `main`
  (done — generated Nov 14).
- The droplet `.env` already filled (R2 creds, DB password, JWT, etc.).

Log in and switch to the deploy user:

```bash
ssh deploy@142.93.208.192
# if you land as root:
sudo su - deploy
```

All commands below run from the repo's `deploy/` directory and **must** include
`--env-file ../.env` (the `.env` lives at the repo root, not in `deploy/`):

```bash
cd ~/Cinematic-Celebration-Apps/deploy
```

---

## 2. Pull the latest code

```bash
cd ~/Cinematic-Celebration-Apps
git pull origin main
```

Rebuild the API so it runs the latest code (build-on-box; do NOT use `pull`):

```bash
cd deploy
docker compose --env-file ../.env up -d --build api
docker compose --env-file ../.env ps
curl -sk https://142.93.208.192.sslip.io/healthz   # expect {"status":"ok"}
```

Frontends (admin + web) rebuild automatically on Cloudflare Pages on push to
`main` — nothing to do on the droplet for them.

---

## 3. BACK UP the current database first (safety net)

Never wipe without a backup. This dumps the current Postgres to a file on the
droplet so you can restore if anything goes wrong.

```bash
cd ~/Cinematic-Celebration-Apps/deploy
mkdir -p ~/db-backups
docker compose --env-file ../.env exec -T postgres \
  pg_dump -U cinematic -d cinematic \
  | gzip > ~/db-backups/pre-migration-$(date +%Y%m%d-%H%M%S).sql.gz
ls -lh ~/db-backups
```

Confirm you see a non-zero-size `.sql.gz` file before continuing.

> **Rollback (only if needed later):** restore with
> `gunzip -c ~/db-backups/<file>.sql.gz | docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic`
> into a freshly emptied DB.

---

## 4. Wipe and recreate an EMPTY schema

The migrator preserves original row IDs (`OVERRIDING SYSTEM VALUE`), so it must
load into an **empty** schema or IDs collide. We reset the schema, then re-apply
all Alembic migrations to get a clean, empty, up-to-date structure.

```bash
cd ~/Cinematic-Celebration-Apps/deploy

# Drop and recreate the public schema (empties ALL tables).
docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-apply every migration into the empty schema (brings it to 0016 / head).
docker compose --env-file ../.env run --rm api alembic upgrade head

# Sanity check: tables exist and bookings is empty.
docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic -c "SELECT count(*) FROM bookings;"   # expect 0
```

---

## 5. Migrate the legacy data (dump-file mode — no MariaDB needed)

Your dump is a phpMyAdmin `.sql` file. The migrator reads it directly with
`dump_to_json.py`; there is **no MariaDB server** to run.

**Why we run on the droplet HOST (not the `api` container):** the `api` Docker
image only contains `apps/api` (app + alembic) and does NOT include the
`scripts/` package or the migration libraries (`pymysql`, `boto3`,
`argon2-cffi`). So we run the scripts in a small Python venv on the host. The
migration also needs to reach Postgres, which is internal-only in compose — so
we temporarily publish its port to localhost for the migration, then remove it.

### 5a. Find the Postgres container's network IP

Postgres is internal-only (not published to the host). Rather than publish a
port, we connect to the container's Docker-network IP directly via
`NEW_DATABASE_URL` (which `config.py` honors as an override). No compose
override, no cleanup needed.

```bash
PG_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' deploy-postgres-1)
echo "PG_IP=$PG_IP"   # e.g. 172.18.0.x
```

If `PG_IP` is empty, the container name differs — list it with
`docker ps --format '{{.Names}}'` and use the postgres one.

### 5b. Set up the migration venv on the host

Needs Python 3.12 on the droplet (`python3 --version`). If missing:
`sudo apt-get update && sudo apt-get install -y python3-venv`.

> **Repo layout note:** on the droplet the repo root is
> `~/Cinematic-Celebration-Apps` with `apps/`, `deploy/`, `scripts/` directly
> under it (there is NO `New_Application/` subfolder — that only exists in the
> local dev checkout). All migration commands run from the repo ROOT, and the
> `.env` lives at the repo root too.

```bash
cd ~/Cinematic-Celebration-Apps
python3 -m venv .mig && . .mig/bin/activate
pip install -r scripts/migrate_from_mariadb/requirements.txt
```

### 5c. Parse the dump into JSON (no DB needed)

```bash
cd ~/Cinematic-Celebration-Apps
rm -rf ./_data            # start clean (removes any leftover JSON from a prior run)
MIGRATION_DATA_DIR=./_data \
  python -m scripts.migrate_from_mariadb.dump_to_json \
    scripts/cine_celebration_data.sql ./_data
ls -la ./_data   # one <table>.json per migrated table
```

Expected: a line per table with row counts (booking, location, plan, slot,
cake, combos, special_decor, occasion, users, user_role, contact_form_leads).

### 5d. Load the JSON into Postgres

Pull the DB password from the root `.env` into a shell variable, then run load.
(`NEW_DB_HOST=127.0.0.1` reaches the port we published in 5a.)

```bash
cd ~/Cinematic-Celebration-Apps
export PGPW="$(grep -E '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)"
echo "pw length: ${#PGPW}"   # must be non-zero

MIGRATION_DATA_DIR=./_data \
NEW_DATABASE_URL="postgresql://cinematic:${PGPW}@${PG_IP}:5432/cinematic" \
  python -m scripts.migrate_from_mariadb.load
```

Expected: `loaded N rows into ...` for each table, a note of any skipped
duplicate-active-slot bookings (the Nov-7 trial skipped ids 2261, 2752, 3070 —
similar skips are normal and fine), and "reset identity sequences".

### 5e. Validate

```bash
cd ~/Cinematic-Celebration-Apps
MIGRATION_DATA_DIR=./_data \
NEW_DATABASE_URL="postgresql://cinematic:${PGPW}@${PG_IP}:5432/cinematic" \
  python -m scripts.migrate_from_mariadb.validate
```

Expected: a row-count table (old → new) and `validate passed: all checks OK.`
If it prints `validate FAILED`, STOP and review the mismatches before going
further (the DB is already loaded; you can re-wipe from step 4 and retry, or
restore the step-3 backup).

### 5f. Clean up the migration venv

```bash
cd ~/Cinematic-Celebration-Apps
deactivate 2>/dev/null || true
# optional: rm -rf .mig _data   (keep _data if you want the parsed JSON around)
```

> Nothing to undo on Postgres — we never published a port; we connected over the
> internal Docker network IP, so the container stays internal-only.

> **Images note:** the dump contains **no image bytes** (the `image` columns are
> empty and there are no base64 blobs). So the image-upload script
> (`upload_images.py`) is skipped on purpose — catalog photos are re-added via
> the admin panel in step 7.

---

## 6. Reset the owner admin password

Every migrated user got a random password hash and `must_reset_password = true`
(plain-text passwords are never copied). Set a known password for the owner so
you can log in. Edit `username` and `new_password`, then paste the whole block:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T api python - <<'PY'
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from sqlalchemy import select

username = "owner"           # <-- set to a real migrated admin username
new_password = "Cinematic@2025"  # <-- choose a strong password

with SessionLocal() as db:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        print(f"NO SUCH USER: {username}")
    else:
        user.password_hash = hash_password(new_password)
        if hasattr(user, "must_reset_password"):
            user.must_reset_password = False
        db.commit()
        print(f"OK: password updated for {username}")
PY
```

To list the migrated admin usernames first:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic \
  -c "SELECT u.username, r.name AS role FROM users u JOIN user_roles r ON r.id=u.role_id ORDER BY r.name, u.username;"
```

---

## 6b. Collapse legacy roles (only if needed)

The migrator maps legacy role names, but older legacy data can still leave
extra `user_roles` rows (e.g. `super admin`, `manager`). Check first:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic -c "SELECT id, name FROM user_roles ORDER BY id;"
```

If you see only `admin` and `staff`, skip this. If you see legacy rows, repoint
users off them then delete the empty rows (FK is `ON DELETE RESTRICT`, so order
matters — adjust the IDs to match the output above):

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres \
  psql -U cinematic -d cinematic <<'SQL'
BEGIN;
UPDATE users SET role_id = 2 WHERE role_id = 1;  -- super admin -> admin
UPDATE users SET role_id = 4 WHERE role_id = 3;  -- manager -> staff
DELETE FROM user_roles WHERE id IN (1, 3);
SELECT ur.id, ur.name, count(u.id) AS users
FROM user_roles ur LEFT JOIN users u ON u.role_id = ur.id
GROUP BY ur.id, ur.name ORDER BY ur.id;
COMMIT;
SQL
```

---

## 7. Re-upload catalog images via the admin panel

The migration brought all records and text, but not image files. Add the
catalog photos through the admin UI (it uploads straight to Cloudflare R2):

1. Open the admin panel: `https://cineceleb-admin.pages.dev`
2. Log in as the owner (password from step 6).
3. Go to **Catalog** → for each **plan**, upload its gallery image(s);
   for **cakes / special decor / combos**, upload each thumbnail.
4. Open the customer site (`https://cineceleb-web.pages.dev`) and confirm the
   images show on the plan/add-on cards.

> You only need to do this once. Images then live in R2 and are served via the
> Pages sites.

---

## 8. Smoke-test the new app on staging URLs (old site still live)

Before any DNS change, confirm the new app works end-to-end with the real data:

- [ ] Admin login works; bookings list shows the migrated bookings.
- [ ] Time sheet and cake sheet render and export to `.xlsx`.
- [ ] Analytics loads.
- [ ] Customer site: create a test booking request — it holds the slot and
      returns a reference token.
- [ ] Catalog images display on the customer site.
- [ ] `curl -sk https://142.93.208.192.sslip.io/healthz` → `{"status":"ok"}`.

If all good, proceed to DNS. If not, fix first — the old site is still serving
customers, so there's no time pressure.

---

## 9. Move DNS to Cloudflare (the cutover)

> **This is the only step that touches the live domain. Do it last, and do it
> carefully.** Moving DNS is FREE. You keep the domain registered at Hostinger;
> you only change *who answers DNS queries* to Cloudflare.

### 9a. Record the current (Hostinger) DNS first — rollback insurance

In Hostinger: **hPanel → Domains → `cinematiccelebration.in` → DNS / Nameservers
→ DNS records.** Take a screenshot / copy EVERY record (A, CNAME, MX, TXT). You
will recreate these in Cloudflare so nothing (email, old site) breaks.

Especially note:
- The **MX** records (email) — missing these breaks email to the domain.
- Any **TXT** records (SPF/DKIM/domain verification).
- The current **A/CNAME** for the apex and `www` (the old live site).

### 9b. Add the domain as a zone in Cloudflare

In Cloudflare: **Add a site / Add a domain → enter `cinematiccelebration.in`**
→ choose the **Free** plan. Cloudflare scans and imports existing records.
**Verify** the imported list matches what you saved in 9a — add any missing MX /
TXT records manually so email and verification keep working.

Cloudflare then shows **two nameservers**, e.g.
`xxx.ns.cloudflare.com` and `yyy.ns.cloudflare.com`. Keep this page open.

### 9c. Add the NEW app's records in Cloudflare (before switching nameservers)

In Cloudflare **DNS → Records**, add:

| Type | Name | Target | Proxy |
|---|---|---|---|
| A | `api` | `142.93.208.192` | DNS only (grey cloud) first; can proxy later |

> Leave the apex and `admin` for the Pages custom-domain step (9e), which adds
> their records for you.

### 9d. Switch nameservers at Hostinger (the actual "move")

In Hostinger: **hPanel → Domains → `cinematiccelebration.in` → Nameservers →
Change / Use custom nameservers.** Replace Hostinger's nameservers with the two
Cloudflare gave you in 9b. Save.

- Propagation takes anywhere from minutes to a few hours.
- Until it finishes, DNS may resolve via either provider — which is why 9b/9c
  recreated all records in Cloudflare first, so nothing goes dark.

### 9e. Attach the real domains to the Cloudflare Pages sites

In Cloudflare **Workers & Pages**:

- Open **cineceleb-web** → **Custom domains** → add `cinematiccelebration.in`
  and `www.cinematiccelebration.in`. Cloudflare creates the needed DNS records
  automatically.
- Open **cineceleb-admin** → **Custom domains** → add
  `admin.cinematiccelebration.in`.

### 9f. Point the frontends and API at the production hostnames

On the droplet, edit `~/Cinematic-Celebration-Apps/.env`:

```
ENVIRONMENT=production
API_HOST=api.cinematiccelebration.in
CORS_ALLOWED_ORIGINS=https://cinematiccelebration.in,https://admin.cinematiccelebration.in
COOKIE_SAMESITE=lax
COOKIE_SECURE=true
```

Apply it and let Caddy issue the real certificate:

```bash
cd ~/Cinematic-Celebration-Apps/deploy
docker compose --env-file ../.env up -d
curl -s https://api.cinematiccelebration.in/healthz   # expect {"status":"ok"} over real HTTPS
```

Rebuild the Pages sites so they call the production API (set the build-time API
URL to `https://api.cinematiccelebration.in` in each Pages project's settings,
then trigger a redeploy / push a commit).

### 9g. Move the uptime monitor

In UptimeRobot, change the monitored URL from the `sslip.io` staging URL to
`https://api.cinematiccelebration.in/healthz`.

---

## 10. Post-cutover verification

- [ ] `https://cinematiccelebration.in` serves the NEW customer site.
- [ ] `https://admin.cinematiccelebration.in` serves the admin panel; login works.
- [ ] `https://api.cinematiccelebration.in/healthz` → `{"status":"ok"}`.
- [ ] A real booking request on the live domain holds a slot and returns a token.
- [ ] Email to the domain still works (MX records carried over).
- [ ] Nightly backup cron is installed and the next run lands in R2.

Keep the step-3 DB backup and the recorded Hostinger DNS values for at least two
weeks as rollback insurance.

---

## Appendix A — troubleshooting the migration

- **`ModuleNotFoundError: scripts`** — you must run from the
  `New_Application/` directory (so the `scripts` package resolves), with the
  venv activated. Re-run `cd ~/Cinematic-Celebration-Apps/New_Application` and
  `. .mig/bin/activate`.
- **`connection refused` on load/validate** — the temporary Postgres port
  (step 5a) isn't up. Re-run the 5a `up -d postgres` with both `-f` files and
  confirm `docker compose ... ps` shows `127.0.0.1:5432->5432`.
- **`password authentication failed`** — `$PGPW` didn't capture the password.
  Check `echo "$PGPW"` is non-empty and matches `POSTGRES_PASSWORD` in `.env`.
- **`validate FAILED` with a count mismatch** — the DB is already loaded. Re-run
  the wipe (step 4) and the load (step 5), or restore the step-3 backup. Do NOT
  proceed to DNS with a failed validation.
- **Duplicate active slots skipped** — `load.py` prints skipped booking IDs;
  these are historical duplicates the new active-slot unique index forbids.
  Review them in the old system; they're intentionally not loaded.

---

## Appendix B — quick rollback

If the new live site misbehaves after DNS cutover and you need the OLD site back
fast: in Hostinger, switch the nameservers back to Hostinger's defaults (from
your 9a notes), or in Cloudflare point the apex/`www` records back at the old
Hostinger server IP. Because you recorded everything in 9a, this is reversible.
