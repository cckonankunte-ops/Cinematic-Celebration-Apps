"""Configuration for the MariaDB -> PostgreSQL migration.

All connection settings come from environment variables so no secrets live in
code. The documented migration constants ("DECIDE" choices) live here too so
they are reviewable in one place.

Source MariaDB (old system):
    OLD_DB_HOST, OLD_DB_PORT, OLD_DB_USER, OLD_DB_PASSWORD, OLD_DB_NAME

Target PostgreSQL (new system):
    NEW_DB_HOST, NEW_DB_PORT, NEW_DB_USER, NEW_DB_PASSWORD, NEW_DB_NAME
    (or a single NEW_DATABASE_URL overriding the parts above)

Cloudflare R2 (public image bucket):
    R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,
    R2_PUBLIC_BUCKET, R2_PUBLIC_PREFIX (optional key prefix),
    IMG_SOURCE_DIR (optional local dir holding old image files)

Working directory for intermediate JSON produced by extract.py:
    MIGRATION_DATA_DIR (default ./_data)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Documented migration decisions ("DECIDE" choices).
# --------------------------------------------------------------------------

# The old system hardcoded a flat Rs.150 charge per extra guest. The new schema
# makes this DB-driven per plan, so every migrated plan gets this value.
EXTRA_GUEST_PAISE: int = 15000  # Rs.150 in paise

# The old `plan` table had no per-plan advance. The new schema requires an
# `advance_paise` acceptance threshold per plan. We seed a documented default;
# staff can tune per-plan values after cutover.
DEFAULT_ADVANCE_PAISE: int = 50000  # Rs.500 in paise

# The old `booking.cakeid` column DEFAULTed to 1 even when no cake was chosen,
# so the value 1 is treated as the "no cake" sentinel: no cake booking_item row
# is produced for it. precheck.py prints what cake id 1 actually is so a human
# can confirm this assumption before loading.
CAKEID_NO_CAKE_SENTINEL: int = 1

# Far-future sentinel used by the old schema for "no end date".
DEFAULT_EFFECTIVE_TO: str = "2099-12-31"
DEFAULT_CAKE_EFFECTIVE_TO: str = "2199-12-31"


@dataclass(frozen=True)
class MariaDBConfig:
    """Source MariaDB connection settings read from the environment."""

    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass(frozen=True)
class PostgresConfig:
    """Target PostgreSQL connection settings read from the environment."""

    host: str
    port: int
    user: str
    password: str
    database: str

    @property
    def conninfo(self) -> str:
        """Return a libpq connection string for psycopg.

        Accepts NEW_DATABASE_URL in either the plain libpq URL form
        (``postgresql://...``) or the SQLAlchemy form
        (``postgresql+psycopg://...``). psycopg.connect() does not understand
        the ``+psycopg`` dialect suffix, so it is stripped here.
        """
        override = os.environ.get("NEW_DATABASE_URL")
        if override:
            return override.replace("postgresql+psycopg://", "postgresql://", 1)
        return (
            f"host={self.host} port={self.port} user={self.user} "
            f"password={self.password} dbname={self.database}"
        )


@dataclass(frozen=True)
class R2Config:
    """Cloudflare R2 (S3-compatible) settings for the public image bucket."""

    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    public_bucket: str
    public_prefix: str = ""
    image_source_dir: str = ""


@dataclass(frozen=True)
class MigrationConfig:
    """Top-level migration configuration bundle."""

    source: MariaDBConfig
    target: PostgresConfig
    r2: R2Config
    data_dir: str = "./_data"
    extra_guest_paise: int = EXTRA_GUEST_PAISE
    default_advance_paise: int = DEFAULT_ADVANCE_PAISE
    cakeid_no_cake_sentinel: int = CAKEID_NO_CAKE_SENTINEL
    _notes: tuple[str, ...] = field(default_factory=tuple)


def _env(name: str, default: str | None = None) -> str:
    """Return a required environment variable, or raise if missing."""
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_config() -> MigrationConfig:
    """Build a MigrationConfig from the current environment variables.

    Raises RuntimeError if a required source/target variable is missing. R2
    variables are only required by upload_images.py; they default to empty so
    the other steps can run without R2 credentials present.
    """
    # Source MariaDB vars are only needed by extract.py (live-server mode).
    # In dump-file mode (dump_to_json.py -> load.py) they are unused, so they
    # default to empty and never block the load step.
    source = MariaDBConfig(
        host=os.environ.get("OLD_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("OLD_DB_PORT", "3306")),
        user=os.environ.get("OLD_DB_USER", ""),
        password=os.environ.get("OLD_DB_PASSWORD", ""),
        database=os.environ.get("OLD_DB_NAME", "cine_celebration"),
    )
    target = PostgresConfig(
        host=_env("NEW_DB_HOST", "127.0.0.1"),
        port=int(_env("NEW_DB_PORT", "5432")),
        user=_env("NEW_DB_USER", "postgres"),
        password=_env("NEW_DB_PASSWORD", ""),
        database=_env("NEW_DB_NAME", "cinematic"),
    )
    r2 = R2Config(
        endpoint_url=os.environ.get("R2_ENDPOINT_URL", ""),
        access_key_id=os.environ.get("R2_ACCESS_KEY_ID", ""),
        secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
        public_bucket=os.environ.get("R2_PUBLIC_BUCKET", ""),
        public_prefix=os.environ.get("R2_PUBLIC_PREFIX", ""),
        image_source_dir=os.environ.get("IMG_SOURCE_DIR", ""),
    )
    return MigrationConfig(
        source=source,
        target=target,
        r2=r2,
        data_dir=os.environ.get("MIGRATION_DATA_DIR", "./_data"),
    )
