"""Extract every old MariaDB table into intermediate JSON files.

Run after precheck.py and before transform/load. Writes one ``<table>.json``
file per source table into the configured data directory (default ./_data).
Uses a PyMySQL DictCursor so rows arrive as plain dicts ready for transform.py.

Usage:
    python -m scripts.migrate_from_mariadb.extract
"""

from __future__ import annotations

import datetime as _dt
import decimal
import json
import os
from typing import Any

from .config import MigrationConfig, load_config

# Old tables to dump, in no particular order (load.py handles ordering).
SOURCE_TABLES: tuple[str, ...] = (
    "location",
    "occasion",
    "plan",
    "slot",
    "cake",
    "special_decor",
    "combos",
    "user_role",
    "users",
    "booking",
    "contact_form_leads",
    "status",
)


def _json_default(value: Any) -> str:
    """Serialize datetime/date/Decimal values that json can't handle natively."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _connect(config: MigrationConfig):  # pragma: no cover - requires a live DB
    """Open a PyMySQL connection with a DictCursor to the source MariaDB."""
    import pymysql
    from pymysql.cursors import DictCursor

    return pymysql.connect(
        host=config.source.host,
        port=config.source.port,
        user=config.source.user,
        password=config.source.password,
        database=config.source.database,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def fetch_table(cursor: Any, table: str) -> list[dict[str, Any]]:
    """Return all rows of a table as a list of dicts (SELECT * FROM table)."""
    cursor.execute(f"SELECT * FROM `{table}`")
    return list(cursor.fetchall())


def write_json(data_dir: str, table: str, rows: list[dict[str, Any]]) -> str:
    """Write rows to ``<data_dir>/<table>.json`` and return the file path."""
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, f"{table}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2, default=_json_default)
    return path


def run(config: MigrationConfig) -> dict[str, int]:  # pragma: no cover - live DB
    """Extract all source tables to JSON; return a {table: row_count} summary."""
    counts: dict[str, int] = {}
    connection = _connect(config)
    try:
        with connection.cursor() as cursor:
            for table in SOURCE_TABLES:
                rows = fetch_table(cursor, table)
                path = write_json(config.data_dir, table, rows)
                counts[table] = len(rows)
                print(f"extracted {len(rows):>6} rows from `{table}` -> {path}")
    finally:
        connection.close()
    return counts


def main() -> None:  # pragma: no cover - CLI entry
    """CLI entry point: extract all tables using environment configuration."""
    config = load_config()
    counts = run(config)
    total = sum(counts.values())
    print(f"\nextract complete: {total} rows across {len(counts)} tables")


if __name__ == "__main__":  # pragma: no cover
    main()
