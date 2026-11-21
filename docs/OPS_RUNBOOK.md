# Operations Runbook (VPS / Staging + Production)

Quick, copy-paste reference for common operational tasks on the VPS. All
commands assume you are logged in as the `deploy` user. If the console shows
`root@...`, switch first:

```bash
sudo su - deploy
```

Everything below runs from the `deploy/` directory and **must** include
`--env-file ../.env` (the `.env` lives at the repo root, not in `deploy/`).
Without it, compose uses wrong/default credentials.

```bash
cd ~/Cinematic-Celebration-Apps/deploy
```

---

## 1. Reset / set a user's password

Passwords are argon2 hashes — you cannot set them with plain SQL. Use the app's
own hashing via a one-off Python snippet inside the running `api` container.

> Preferred: do this from the admin panel (Staff page -> Reset password). Use
> the command below only when the UI isn't available.

Edit `username` and `new_password`, then paste the **whole block** (the line
breaks matter — Python is indentation-sensitive, do not collapse it to one line):

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T api python - <<'PY'
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from sqlalchemy import select

username = "sanjay_admin"
new_password = "cck_2025"

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

Expected output: `OK: password updated for sanjay_admin`.
If you see `NO SUCH USER`, list the exact usernames:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic -c "SELECT username FROM users ORDER BY username;"
```

---

## 2. Seed / recreate the owner admin

Creates (or leaves intact) the owner admin + base locations. Idempotent for the
admin user.

```bash
cd ~/Cinematic-Celebration-Apps/deploy && \
  SEED_ADMIN_USERNAME=owner SEED_ADMIN_PASSWORD='Cinematic@2025' \
  docker compose --env-file ../.env run --rm \
    -e SEED_ADMIN_USERNAME -e SEED_ADMIN_PASSWORD \
    api python -m app.jobs.seed_min
```

> Known issue: if the catalog already has multiple plans, `seed_min` may raise
> `MultipleResultsFound` after creating the admin. The admin is created first,
> so the reset still succeeds. Tracked in FUTURE_WORK.md.

---

## 3. Role cleanup (collapse legacy roles to admin/staff)

Only needed once, on a DB migrated before the role-mapping fix. Repoint users
off the legacy role rows, then delete the now-empty rows (FK is
`ON DELETE RESTRICT`, so order matters). Confirm the IDs first:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic -c "SELECT id, name FROM user_roles ORDER BY id;"
```

Then (adjust IDs if they differ):

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic <<'SQL'
BEGIN;
UPDATE users SET role_id = 2 WHERE role_id = 1;  -- super admin -> admin
UPDATE users SET role_id = 4 WHERE role_id = 3;  -- manager -> staff
DELETE FROM user_roles WHERE id IN (1, 3);
SELECT ur.id, ur.name, count(u.id) AS users
FROM user_roles ur
LEFT JOIN users u ON u.role_id = ur.id
GROUP BY ur.id, ur.name
ORDER BY ur.id;
COMMIT;
SQL
```

---

## 4. Container status & health

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env ps
curl -sk https://142.93.208.192.sslip.io/healthz
```

Logs:

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env logs --tail=50 api
```

---

## 5. Deploy latest code

```bash
cd ~/Cinematic-Celebration-Apps && git pull
cd deploy && docker compose --env-file ../.env up -d --build api
```

Frontends (admin + web) auto-build on Cloudflare Pages on push to `main`.

---

## 6. Run the one-off jobs manually

```bash
# expire pending bookings (also runs every minute via cron)
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T api python -m app.jobs.expire_pending

# auto-close stale leads (daily via cron; does nothing while LEAD_AUTO_CLOSE_DAYS=0)
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T api python -m app.jobs.auto_close_leads
```

---

## 7. Read-only DB access (safe inspection)

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic
```

Prefer the admin panel + API for any change to users, money, or bookings. Use
`psql` for read-only inspection only — never hand-edit those tables.

---

## 8. Lead CRM (lead-crm spec)

### Public endpoints (deliberately unauthenticated, rate-limited per IP)

These are the only public lead routes. They return just a token or a fixed
message, never lead data.

| Route | Limit | Used by |
|---|---|---|
| `POST /api/v1/public/leads` | 10/min | Booking wizard Step 1 (returns a lead token) |
| `POST /api/v1/public/enquiries` | 5/min | Homepage quick enquiry, Contact page form |
| `POST /api/v1/public/enquiry-codes` | 10/min | WhatsApp links (enquiry code + source, no personal data) |
| `POST /api/v1/public/contact` | 5/min | Legacy contact form; now saved as a `contact_form` lead |

Every `/api/v1/admin/leads/...` route needs a session with the `admin` or
`receptionist` role; receptionists see only their branch, and `staff` get 403.
`/api/v1/admin/leads/dashboard` is admin-only.

### Roles

| Role | Can do |
|---|---|
| `admin` | Everything, all branches |
| `staff` | Bookings, payments, time and cake sheets for their branch (no leads) |
| `receptionist` | Everything staff can do, plus Leads for their branch |

Migration `0025_add_receptionist_role` adds the role. Give it to people in
**Staff** (admin panel): pick the role and branch on their row. The change
applies when that person next logs in.

### Server settings (`.env`, not editable in the admin panel)

| Variable | Default | Meaning |
|---|---|---|
| `LEAD_RESPONSE_ALERT_MINUTES` | `10` | A new lead not contacted for this long is shown in red ("Not contacted · N min") and counted in the red nav badge |
| `LEAD_AUTO_CLOSE_DAYS` | `0` | `0` = never auto-close. Otherwise the daily job closes `new`/`contacted`/`follow_up` leads with no activity for this many days (and no future follow-up) as Lost / No response |

Change a value by editing `.env`, then `docker compose --env-file ../.env up -d api`.
The cron job reads `LEAD_AUTO_CLOSE_DAYS` on every run.

### Cron

Add the auto-close line to the host crontab (`crontab -e`), next to the
existing `expire_pending` line (`crontab -l` shows it). Copy that line's path
and log folder; only the job name, schedule and log file change. 21:30 UTC is
03:00 IST:

```cron
30 21 * * * cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T api python -m app.jobs.auto_close_leads >> <same log folder as expire_pending>/leads.log 2>&1
```

(`deploy/cron/crontab` holds the same schedule with a placeholder path.) It is
safe to install while `LEAD_AUTO_CLOSE_DAYS=0`: the job logs `closed=0` and exits.

### Deploying lead-crm (migration `0024`)

`0024_create_leads_crm` creates `leads`, `lead_activities`, `enquiry_codes`,
adds `locations.whatsapp_phone`, and copies `contact_leads` rows into leads
(`contact_leads` itself is left untouched). `0025_add_receptionist_role` adds
the receptionist role. `alembic upgrade head` applies both.

**Order matters: backend first, then merge.** Cloudflare Pages rebuilds the
admin and website as soon as `main` changes, and the new pages call the new
API. The new API works with the old pages, so deploy the API from the branch,
then merge the PR.

```bash
cd ~/Cinematic-Celebration-Apps
# 0. Note the current commit (for rollback) and check memory
git rev-parse --short HEAD
free -h
# 1. Backup first
cd deploy
docker compose --env-file ../.env exec -T postgres pg_dump -U cinematic -d cinematic -Fc > ~/pre_0024_$(date +%F).dump
ls -lh ~/pre_0024_*.dump
# 2. Get the branch and build the new image (old API keeps serving meanwhile)
cd .. && git fetch origin && git checkout feat/lead-crm && git pull --ff-only
cd deploy && docker compose --env-file ../.env build api
# 3. Migrate with the NEW image before it serves traffic (0024 + 0025)
docker compose --env-file ../.env run --rm api alembic upgrade head
docker compose --env-file ../.env run --rm api alembic current      # expect 0025 (head)
# 4. Switch the API to the new image
docker compose --env-file ../.env up -d api
# 5. Check
curl -fsS https://api.cinematiccelebration.in/healthz
docker compose --env-file ../.env logs --tail=30 api
docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic \
  -c "SELECT source, count(*) FROM leads GROUP BY 1;" \
  -c "SELECT name FROM user_roles ORDER BY id;"
# 6. Merge the PR on GitHub (Pages builds admin + web), then move the server to main
cd .. && git checkout main && git pull --ff-only
```

Roll back (if needed), before anyone is given the Receptionist role:

```bash
cd ~/Cinematic-Celebration-Apps/deploy
docker compose --env-file ../.env run --rm api alembic downgrade 0023   # drops lead tables + column
cd .. && git checkout <commit from step 0> && cd deploy
docker compose --env-file ../.env build api && docker compose --env-file ../.env up -d api
```

`0025`'s downgrade refuses while any user has the receptionist role (move them
back to staff first). Restoring the step-1 dump is the other way back.

### After deploy

- In **Staff**, change the people who handle enquiries to **Receptionist**.
  Until then only admins can open Leads.
- In **Catalog → Location settings**, set a **Branch WhatsApp number** for every
  branch. It is used for the website WhatsApp links and the "Send today's
  follow-ups" message. Without it the branch phone is used, and a landline
  written as `080 …` looks like a mobile number, so WhatsApp would open a chat
  that cannot be delivered.
- Logs contain only codes, ids and counts for leads (no phone, name or notes).

---

## Notes

- Always include `--env-file ../.env`.
- `psql` heredocs and the Python heredoc in section 1 must keep their real line
  breaks — do not paste them as a single collapsed line.
- Rotate all secrets (DB password, JWT secret, R2 keys, owner password) before
  production cutover; the staging values were shared in plaintext during setup.
