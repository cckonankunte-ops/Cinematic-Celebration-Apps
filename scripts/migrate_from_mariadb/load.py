"""Load transformed records into PostgreSQL via psycopg, in dependency order.

Reads the intermediate JSON produced by extract.py, applies the pure
transforms from transform.py, and inserts into the new schema inside
transactions. Insert order respects foreign keys:

    locations -> user_roles -> users -> plans -> plan_gallery_images -> slots
    -> occasions -> cakes -> special_decor_items -> combo_items -> bookings
    -> booking_items -> payments -> booking_events -> contact_leads

Original ids are preserved so FK references line up. A 'created' booking_event
is seeded per migrated booking. Passwords are never copied: each user gets a
fresh random argon2 hash and must reset on first login.

Usage:
    python -m scripts.migrate_from_mariadb.load
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Any

from . import transform as T
from .config import MigrationConfig, load_config


def _read(data_dir: str, table: str) -> list[dict[str, Any]]:
    """Read an extracted ``<table>.json`` file (empty list if absent)."""
    path = os.path.join(data_dir, f"{table}.json")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _price_lookup(records: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index transformed catalog records by id for booking_items snapshots."""
    return {int(r["id"]): r for r in records}


def _hash_random_password() -> str:
    """Return an argon2 hash of a throwaway random password (never stored plain).

    Uses the SAME argon2 params as the app (m=19456, t=2, p=1) without importing
    the app package.
    """
    from argon2 import PasswordHasher

    hasher = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)
    return hasher.hash(secrets.token_urlsafe(24))


def build_records(config: MigrationConfig) -> dict[str, list[dict[str, Any]]]:
    """Transform all extracted JSON into new-shape records keyed by table name."""
    data_dir = config.data_dir
    roles_raw = _read(data_dir, "user_role")
    role_by_id = {int(r["id"]): T.transform_user_role(r)["name"] for r in roles_raw}

    cakes = [T.transform_cake(r) for r in _read(data_dir, "cake")]
    decor = [T.transform_special_decor(r) for r in _read(data_dir, "special_decor")]
    combos = [T.transform_combo(r) for r in _read(data_dir, "combos")]
    cake_lookup = _price_lookup(cakes)
    decor_lookup = _price_lookup(decor)
    combo_lookup = _price_lookup(combos)

    plans_raw = _read(data_dir, "plan")
    gallery: list[dict[str, Any]] = []
    for plan_row in plans_raw:
        gallery.extend(T.transform_plan_gallery(plan_row))

    users = [
        T.transform_user(
            u, role_by_id.get(int(u["roleid"]), "staff"), _hash_random_password()
        )
        for u in _read(data_dir, "users")
    ]

    bookings: list[dict[str, Any]] = []
    booking_items: list[dict[str, Any]] = []
    payments: list[dict[str, Any]] = []
    used_refs: set[str] = set()
    for b in _read(data_dir, "booking"):
        booking = T.transform_booking(b, used_references=used_refs)
        bookings.append(booking)
        for item in T.build_booking_items(
            b, cake_lookup=cake_lookup, decor_lookup=decor_lookup, combo_lookup=combo_lookup
        ):
            booking_items.append({"booking_id": booking["id"], **item})
        for pay in T.build_payments(b):
            payments.append({"booking_id": booking["id"], **pay})

    return {
        "locations": [T.transform_location(r) for r in _read(data_dir, "location")],
        "user_roles": [T.transform_user_role(r) for r in roles_raw],
        "users": users,
        "plans": [T.transform_plan(r) for r in plans_raw],
        "plan_gallery_images": gallery,
        "slots": [T.transform_slot(r) for r in _read(data_dir, "slot")],
        "occasions": [T.transform_occasion(r) for r in _read(data_dir, "occasion")],
        "cakes": cakes,
        "special_decor_items": decor,
        "combo_items": combos,
        "bookings": bookings,
        "booking_items": booking_items,
        "payments": payments,
        "contact_leads": [
            T.transform_contact_lead(r) for r in _read(data_dir, "contact_form_leads")
        ],
    }


# Column order per table for INSERT statements (ids preserved via OVERRIDING).
_INSERT_COLUMNS: dict[str, tuple[str, ...]] = {
    "locations": ("id", "name", "slug", "address", "phone", "is_active"),
    "user_roles": ("id", "name"),
    "users": ("id", "username", "password_hash", "role_id", "location_id", "is_active"),
    "plans": (
        "id", "location_id", "title", "description", "details", "plan_type",
        "price_paise", "people_allowed", "max_people_allowed", "extra_guest_paise",
        "give_discount", "max_discount_paise", "advance_paise", "effective_from",
        "effective_to", "is_active",
    ),
    "plan_gallery_images": ("plan_id", "object_key", "sort_order"),
    "slots": (
        "id", "plan_id", "description", "show_combos", "sort_order",
        "effective_from", "effective_to", "is_active",
    ),
    "occasions": ("id", "location_id", "name", "is_active"),
    "cakes": (
        "id", "location_id", "description", "price_paise", "object_key",
        "effective_from", "effective_to", "is_active",
    ),
    "special_decor_items": (
        "id", "location_id", "name", "description", "price_paise", "object_key",
        "sort_order", "effective_from", "effective_to", "is_active",
    ),
    "combo_items": (
        "id", "location_id", "name", "description", "price_paise", "object_key",
        "effective_from", "effective_to", "is_active",
    ),
    "bookings": (
        "id", "booking_reference", "public_token", "location_id", "plan_id",
        "slot_id", "booking_date", "booking_name", "email", "phone",
        "special_person_name", "name_on_cake", "message", "people", "occasion_id",
        "plan_price_paise", "subtotal_paise", "discount_paise", "food_paise",
        "other_paise", "cleaning_paise", "total_paise", "advance_paise", "status",
        "crm_user_id", "created_at",
    ),
    "booking_items": ("booking_id", "kind", "item_id", "name_snapshot", "price_paise"),
    "payments": (
        "booking_id", "method", "amount_paise", "received_at", "provider",
        "provider_ref", "note",
    ),
    "contact_leads": ("id", "name", "phone", "email", "message", "created_at"),
}

# Identity tables where original ids are forced via OVERRIDING SYSTEM VALUE.
_IDENTITY_TABLES = frozenset(
    {
        "locations", "user_roles", "users", "plans", "slots", "occasions",
        "cakes", "special_decor_items", "combo_items", "bookings", "contact_leads",
    }
)

# Order matters: parents before children.
_LOAD_ORDER: tuple[str, ...] = (
    "locations", "user_roles", "users", "plans", "plan_gallery_images", "slots",
    "occasions", "cakes", "special_decor_items", "combo_items", "bookings",
    "booking_items", "payments", "contact_leads",
)


def _resolve_role_ids(records: dict[str, list[dict[str, Any]]]) -> None:
    """Attach role_id to user records from the role name -> id mapping."""
    role_id_by_name = {r["name"]: int(r["id"]) for r in records["user_roles"]}
    fallback = next(iter(role_id_by_name.values()), None)
    for user in records["users"]:
        user["role_id"] = role_id_by_name.get(user["role"], fallback)


def _insert_sql(table: str, columns: tuple[str, ...]) -> str:
    """Build an INSERT statement, overriding identity ids where needed."""
    cols = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    overriding = " OVERRIDING SYSTEM VALUE" if table in _IDENTITY_TABLES else ""
    return f"INSERT INTO {table} ({cols}){overriding} VALUES ({placeholders})"


def _booking_events(bookings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Seed one 'created' booking_event per migrated booking."""
    return [
        {"booking_id": b["id"], "event_type": "created", "created_at": b["created_at"]}
        for b in bookings
    ]


def run(config: MigrationConfig) -> dict[str, int]:  # pragma: no cover - live DB
    """Insert all records into PostgreSQL in dependency order; return counts.

    Bookings are inserted individually under savepoints: any booking that would
    violate the active-slot unique index (duplicate pending/accepted booking for
    the same location+slot+date among historical data) is SKIPPED and reported,
    rather than failing the whole migration. Skipped booking ids are excluded
    from booking_items, payments, and booking_events.
    """
    import psycopg
    from psycopg.errors import UniqueViolation

    records = build_records(config)
    _resolve_role_ids(records)
    counts: dict[str, int] = {}
    skipped_booking_ids: set[int] = set()

    with psycopg.connect(config.target.conninfo) as conn:
        with conn.cursor() as cur:
            for table in _LOAD_ORDER:
                columns = _INSERT_COLUMNS[table]
                sql = _insert_sql(table, columns)

                if table == "bookings":
                    loaded = 0
                    for row in records["bookings"]:
                        try:
                            with conn.transaction():
                                cur.execute(sql, [row.get(c) for c in columns])
                            loaded += 1
                        except UniqueViolation:
                            skipped_booking_ids.add(int(row["id"]))
                    counts["bookings"] = loaded
                    print(f"loaded {loaded:>6} rows into bookings "
                          f"({len(skipped_booking_ids)} skipped as duplicate active slot)")
                    continue

                if table in ("booking_items", "payments"):
                    rows = [
                        r for r in records[table]
                        if int(r["booking_id"]) not in skipped_booking_ids
                    ]
                else:
                    rows = records[table]

                for row in rows:
                    cur.execute(sql, [row.get(c) for c in columns])
                counts[table] = len(rows)
                print(f"loaded {len(rows):>6} rows into {table}")

            events = [
                e for e in _booking_events(records["bookings"])
                if e["booking_id"] not in skipped_booking_ids
            ]
            cur.executemany(
                "INSERT INTO booking_events (booking_id, event_type, created_at) "
                "VALUES (%s, %s, %s)",
                [(e["booking_id"], e["event_type"], e["created_at"]) for e in events],
            )
            counts["booking_events"] = len(events)
            print(f"loaded {len(events):>6} rows into booking_events")

        conn.commit()

    if skipped_booking_ids:
        print("\nSkipped booking ids (duplicate active slot) for manual review:")
        print(", ".join(str(i) for i in sorted(skipped_booking_ids)))
    return counts


def main() -> None:  # pragma: no cover - CLI entry
    """CLI entry point: load all records using environment configuration."""
    run(load_config())


if __name__ == "__main__":  # pragma: no cover
    main()
