# MariaDB → PostgreSQL data migration

One-off migration of the legacy Cinematic Celebration system (MariaDB, old
`cine_celebration` schema) into the new PostgreSQL 16 schema.

These scripts are **standalone**. They are intentionally kept **out of the
FastAPI app package** and never import the app. They are run manually, in order,
on the migration machine.

## Prerequisites

```bash
cd New_Application/scripts/migrate_from_mariadb
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

The target PostgreSQL database must already have the schema applied
(`alembic upgrade head` in `apps/api`) before `load.py` runs.

Run the modules from the `New_Application` directory so the package import path
resolves, e.g. `python -m scripts.migrate_from_mariadb.precheck`.

## Environment variables

Source MariaDB:

| Variable | Default | Notes |
|---|---|---|
| `OLD_DB_HOST` | `127.0.0.1` | |
| `OLD_DB_PORT` | `3306` | |
| `OLD_DB_USER` | — (required) | |
| `OLD_DB_PASSWORD` | — (required) | |
| `OLD_DB_NAME` | `cine_celebration` | |

Target PostgreSQL (either the parts, or a single URL):

| Variable | Default | Notes |
|---|---|---|
| `NEW_DB_HOST` | `127.0.0.1` | |
| `NEW_DB_PORT` | `5432` | |
| `NEW_DB_USER` | `postgres` | |
| `NEW_DB_PASSWORD` | `` | |
| `NEW_DB_NAME` | `cinematic` | |
| `NEW_DATABASE_URL` | — | if set, overrides all `NEW_DB_*` parts |

Cloudflare R2 public bucket (only needed for `upload_images.py`):

| Variable | Notes |
|---|---|
| `R2_ENDPOINT_URL` | S3-compatible endpoint |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | credentials |
| `R2_PUBLIC_BUCKET` | public image bucket |
| `R2_PUBLIC_PREFIX` | optional key prefix |
| `IMG_SOURCE_DIR` | optional local dir holding old image files |

Working dir for intermediate JSON: `MIGRATION_DATA_DIR` (default `./_data`).

## Run order

```bash
# 1. Pre-migration checks (exits non-zero if duplicate active slots exist)
python -m scripts.migrate_from_mariadb.precheck

# 2. Extract every old table to ./_data/*.json
python -m scripts.migrate_from_mariadb.extract

# 3. Upload catalog/gallery images to the public R2 bucket (record object keys)
python -m scripts.migrate_from_mariadb.upload_images

# 4. Load transformed records into PostgreSQL (transform.py is applied here)
python -m scripts.migrate_from_mariadb.load

# 5. Validate (exits non-zero on any mismatch)
python -m scripts.migrate_from_mariadb.validate
```

`transform.py` holds the pure, importable, unit-tested mapping logic and is
invoked by `load.py`; it has no CLI of its own.

## Pre-checks (must be resolved before loading)

1. **Duplicate active slots.** The new partial unique index
   `uq_bookings_active_slot` allows only one `pending`/`accepted` booking per
   `(location_id, slot_id, booking_date)`. `precheck.py` lists any conflicting
   groups in the old data and **exits non-zero** — resolve them manually
   (cancel/reject the extras) before loading.
2. **Legacy `cakeid = 1`.** The old `booking.cakeid` column defaulted to `1`
   even when no cake was chosen, so `1` is treated as a **"no cake" sentinel**.
   `precheck.py` prints the cake row with `id = 1` and the count of bookings
   using `cakeid = 1` so a human can confirm the assumption before load.

## Documented migration decisions ("DECIDE" choices)

All constants live in `config.py`:

- **`EXTRA_GUEST_PAISE = 15000` (Rs.150).** The old system hardcoded a flat
  Rs.150 per extra guest. The new schema is DB-driven per plan, so every
  migrated plan is seeded with this value.
- **`DEFAULT_ADVANCE_PAISE = 50000` (Rs.500).** The old `plan` table had no
  per-plan advance. The new schema needs an `advance_paise` acceptance
  threshold per plan, so each plan is seeded with this documented default;
  staff can tune per-plan values after cutover.
- **Booking advance snapshot** uses `max(advanceamount × 100, 0)` from the
  booking row as the historical `bookings.advance_paise` snapshot.
- **`CAKEID_NO_CAKE_SENTINEL = 1`.** `cakeid = 1` (and NULL/0) produces no cake
  `booking_item` row.
- **Money** columns are rupee integers in the old schema; all are converted to
  paise with `× 100`.
- **Status** `statusid` 1/2/3 → `pending`/`accepted`/`rejected`. No old value
  maps to `expired`.
- **Passwords (force-reset, recommended).** Plain-text passwords are **never**
  copied. Each migrated user gets a fresh **random argon2 hash** (same params as
  the app: `m=19456, t=2, p=1`) and `must_reset_password = true`. All users must
  reset their password on first login.
- **Dropped:** legacy decor booleans (`tabledecor`, `foggyrosepetalpath`,
  `balloondecor`, `rosebouquet`, `photoprop`, `gloosyphoto`) and `couponcode`.

## Cutover plan

1. Put the old system in **read-only** mode.
2. Run `precheck.py`; resolve duplicates and confirm the `cakeid = 1` question.
3. Run `extract` → `upload_images` → `load` → `validate`.
4. Point DNS at the new system.
5. **Rollback criterion:** if `validate.py` fails, or the error / failed-booking
   rate exceeds the agreed threshold within the first 24 hours, revert DNS to
   the old (read-only) system and investigate.
6. Keep the old system **read-only for 2 weeks** after cutover (not archived
   immediately) as a fallback and reference.

## Caveats

- `object_key` values in catalog/gallery records start as the raw old image
  reference; `upload_images.py` replaces them with real R2 keys. When no local
  file is found for a path/URL reference, only a derived key is stored (no bytes
  uploaded) — review these keys after migration.
- Original integer ids are preserved (`OVERRIDING SYSTEM VALUE`) so foreign-key
  references line up; run the migration into a freshly-migrated, empty schema.
- `load.py` seeds one `created` booking_event per migrated booking.
