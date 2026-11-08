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
```

---

## 7. Read-only DB access (safe inspection)

```bash
cd ~/Cinematic-Celebration-Apps/deploy && docker compose --env-file ../.env exec -T postgres psql -U cinematic -d cinematic
```

Prefer the admin panel + API for any change to users, money, or bookings. Use
`psql` for read-only inspection only — never hand-edit those tables.

---

## Notes

- Always include `--env-file ../.env`.
- `psql` heredocs and the Python heredoc in section 1 must keep their real line
  breaks — do not paste them as a single collapsed line.
- Rotate all secrets (DB password, JWT secret, R2 keys, owner password) before
  production cutover; the staging values were shared in plaintext during setup.
