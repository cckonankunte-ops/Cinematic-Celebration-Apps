"""Pure transformation logic: old (MariaDB) shapes -> new (PostgreSQL) shapes.

This module is deliberately free of DB and network calls so it is importable
and unit-testable anywhere (its tests have no external dependencies). Every
mapping described in the design's "Data Migration Strategy" is applied here:

- money rupees -> integer paise (x100)
- statusid 1/2/3 -> 'pending'/'accepted'/'rejected'
- location name -> slug; status -> is_active
- people varchar -> int (default 1 on failure)
- specialdecorselected / combosselected JSON + cakeid -> booking_items
- upipayment / cashadvance / onlinepayment > 0 -> payments rows
- legacy decor booleans and couponcode dropped
- public_token generated; booking_reference kept (deduped on collision)

Callers (load.py / transform CLI) supply catalog lookup maps built from the
extracted JSON so this module stays side-effect free.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timezone
from typing import Any

from .config import (
    CAKEID_NO_CAKE_SENTINEL,
    DEFAULT_ADVANCE_PAISE,
    EXTRA_GUEST_PAISE,
)

# Old statusid -> new booking status enum value.
STATUS_MAP: dict[int, str] = {1: "pending", 2: "accepted", 3: "rejected"}

# Old user_role.description (lowercased) -> new role name.
ROLE_MAP: dict[str, str] = {"admin": "admin", "staff": "staff"}


# --------------------------------------------------------------------------
# Small pure helpers
# --------------------------------------------------------------------------


def rupees_to_paise(rupees: Any) -> int:
    """Convert a rupee amount (int/str/float/None) to integer paise (x100).

    None, empty strings, and unparseable values become 0. Floats are rounded to
    the nearest paise. The old columns are rupee integers, so this is lossless
    for the common case.
    """
    if rupees is None or rupees == "":
        return 0
    try:
        return round(float(rupees) * 100)
    except (TypeError, ValueError):
        return 0


def slugify(name: str) -> str:
    """Derive a URL slug: lowercase, spaces -> hyphens, strip non-alnum.

    Example: "Electronic City" -> "electronic-city".
    """
    lowered = (name or "").strip().lower()
    # Replace any run of non-alphanumeric characters with a single hyphen.
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered)
    return hyphenated.strip("-")


def status_to_is_active(status: Any) -> bool:
    """Map an old numeric `status`/`statusid` flag to a boolean is_active.

    The old `location.status` is a tinyint where 1 means active. Any truthy,
    exactly-1 value is active; everything else (0, NULL) is inactive.
    """
    try:
        return int(status) == 1
    except (TypeError, ValueError):
        return False


def parse_people(value: Any) -> int:
    """Parse the old `people` varchar into an int, defaulting to 1 on failure."""
    if value is None:
        return 1
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return 1
    return parsed if parsed >= 1 else 1


def parse_id_list(raw: Any) -> list[int]:
    """Parse a JSON array of IDs (or CSV-ish fallback) into a list of ints.

    The old `specialdecorselected` / `combosselected` columns are longtext
    holding a JSON array like "[1, 3]". Handles None, empty, already-list, and
    a comma-separated fallback. Non-integer entries are skipped.
    """
    if raw is None or raw == "":
        return []
    values: Any = raw
    if isinstance(raw, str):
        try:
            values = json.loads(raw)
        except (ValueError, TypeError):
            values = [p for p in re.split(r"[,\s]+", raw.strip("[]")) if p]
    if isinstance(values, (int, float)):
        values = [values]
    if not isinstance(values, (list, tuple)):
        return []
    out: list[int] = []
    for item in values:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def is_real_cake(cakeid: Any) -> bool:
    """Return True if `cakeid` refers to a real cake (not the 'no cake' sentinel).

    The old schema defaulted cakeid to 1 even when no cake was chosen, so 1 is
    treated as "no cake". NULL/0/unparseable are also treated as "no cake".
    """
    if cakeid is None:
        return False
    try:
        value = int(cakeid)
    except (TypeError, ValueError):
        return False
    return value > 0 and value != CAKEID_NO_CAKE_SENTINEL


def to_utc_isoformat(value: Any) -> str | None:
    """Normalize an old timestamp to a UTC ISO-8601 string (or None).

    Accepts datetime objects (assumed UTC if naive, since the old dump sets
    time_zone='+00:00') and strings. Returns None for falsy input.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def generate_public_token() -> str:
    """Generate a public lookup token (>=16 url-safe chars)."""
    return secrets.token_urlsafe(12)


# --------------------------------------------------------------------------
# Record transformers
# --------------------------------------------------------------------------


def transform_location(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `location` row to a new `locations` record."""
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "slug": slugify(row["name"]),
        "address": row.get("address"),
        "phone": row.get("phone"),
        "is_active": status_to_is_active(row.get("status")),
    }


def transform_occasion(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `occasion` row to a new `occasions` record (description->name)."""
    return {
        "id": int(row["id"]),
        "location_id": int(row["locationid"]),
        "name": row["description"],
        "is_active": True,
    }


def transform_user_role(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `user_role` row to a new `user_roles` record."""
    description = str(row.get("description", "")).strip().lower()
    return {"id": int(row["id"]), "name": ROLE_MAP.get(description, description)}


def transform_plan(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `plan` row to a new `plans` record (money x100, DB-driven rules)."""
    return {
        "id": int(row["id"]),
        "location_id": int(row["locationid"]),
        "title": row["title"],
        "description": row.get("description"),
        "details": row.get("details"),
        "plan_type": int(row.get("plantype", 0)),
        "price_paise": rupees_to_paise(row.get("amount")),
        "people_allowed": int(row.get("peopleallowed", 4)),
        "max_people_allowed": int(row.get("maxpeopleallowed", 0)),
        "extra_guest_paise": EXTRA_GUEST_PAISE,
        "give_discount": bool(int(row.get("givediscount", 0) or 0)),
        "max_discount_paise": rupees_to_paise(row.get("maxdiscount")),
        "advance_paise": DEFAULT_ADVANCE_PAISE,
        "effective_from": to_utc_isoformat(row.get("effectivedate")),
        "effective_to": to_utc_isoformat(row.get("enddate")),
        "is_active": True,
    }


def transform_plan_gallery(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand a plan's `galleryimages` JSON into plan_gallery_images records.

    `object_key` is left as the raw reference; upload_images.py replaces it with
    the uploaded R2 object key. Each entry keeps its position as sort_order.
    """
    refs = row.get("galleryimages")
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except (ValueError, TypeError):
            refs = []
    if not isinstance(refs, (list, tuple)):
        return []
    return [
        {"plan_id": int(row["id"]), "object_key": str(ref), "sort_order": i}
        for i, ref in enumerate(refs)
        if ref
    ]


def transform_slot(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `slot` row to a new `slots` record."""
    return {
        "id": int(row["id"]),
        "plan_id": int(row["planid"]),
        "description": row["description"],
        "show_combos": bool(int(row.get("showcombo", 1) or 0)),
        "sort_order": int(row.get("orderby", 0)),
        "effective_from": to_utc_isoformat(row.get("effectivedate")),
        "effective_to": to_utc_isoformat(row.get("enddate")),
        "is_active": True,
    }


def transform_cake(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `cake` row to a new `cakes` record (image -> object_key later)."""
    return {
        "id": int(row["id"]),
        "location_id": int(row["locationid"]),
        "description": row["description"],
        "price_paise": rupees_to_paise(row.get("amount")),
        "object_key": row.get("image") or "",
        "effective_from": to_utc_isoformat(row.get("effectivedate")),
        "effective_to": to_utc_isoformat(row.get("enddate")),
        "is_active": True,
    }


def transform_special_decor(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `special_decor` row to a new `special_decor_items` record."""
    return {
        "id": int(row["id"]),
        "location_id": int(row["locationid"]),
        "name": row["name"],
        "description": row.get("description") or "",
        "price_paise": rupees_to_paise(row.get("amount")),
        "object_key": row.get("image") or "",
        "sort_order": int(row.get("orderby", 0)),
        "effective_from": to_utc_isoformat(row.get("effectivedate")),
        "effective_to": to_utc_isoformat(row.get("enddate")),
        "is_active": True,
    }


def transform_combo(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `combos` row to a new `combo_items` record."""
    return {
        "id": int(row["id"]),
        "location_id": int(row["locationid"]),
        "name": row["name"],
        "description": row.get("description") or "",
        "price_paise": rupees_to_paise(row.get("amount")),
        "object_key": row.get("image") or "",
        "effective_from": to_utc_isoformat(row.get("effectivedate")),
        "effective_to": to_utc_isoformat(row.get("enddate")),
        "is_active": True,
    }


def transform_contact_lead(row: dict[str, Any]) -> dict[str, Any]:
    """Map an old `contact_form_leads` row to a new `contact_leads` record."""
    return {
        "id": int(row["id"]),
        "name": row["name"],
        "phone": row["phone"],
        "email": row["email"],
        "message": row["message"],
        "created_at": to_utc_isoformat(row.get("createts")),
    }


def transform_user(row: dict[str, Any], role_name: str, password_hash: str) -> dict[str, Any]:
    """Map an old `users` row to a new `users` record.

    The plain-text password is NEVER copied. `password_hash` must be a fresh,
    random argon2 hash supplied by the caller, and `must_reset_password` flags
    that the user must reset on first login. `location_id` is kept; a NULL/0 old
    value becomes None (admin convention = all locations).
    """
    old_location = row.get("locationid")
    try:
        location_id: int | None = int(old_location) if old_location else None
    except (TypeError, ValueError):
        location_id = None
    if location_id == 0:
        location_id = None
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "password_hash": password_hash,
        "role": role_name,
        "location_id": location_id,
        "is_active": True,
        "must_reset_password": True,
    }


def build_booking_items(
    row: dict[str, Any],
    *,
    cake_lookup: dict[int, dict[str, Any]],
    decor_lookup: dict[int, dict[str, Any]],
    combo_lookup: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive booking_items rows from a booking's cake/decor/combo selections.

    Lookups map catalog id -> {name/description, price_paise} drawn from the
    already-transformed catalog so name + price snapshots are captured at
    migration time. The cakeid sentinel ("no cake") produces no cake row.
    """
    items: list[dict[str, Any]] = []

    cakeid = row.get("cakeid")
    if is_real_cake(cakeid):
        cake = cake_lookup.get(int(cakeid))
        if cake is not None:
            items.append(
                {
                    "kind": "cake",
                    "item_id": int(cakeid),
                    "name_snapshot": cake.get("description") or cake.get("name") or "Cake",
                    "price_paise": int(cake.get("price_paise", 0)),
                }
            )

    for decor_id in parse_id_list(row.get("specialdecorselected")):
        decor = decor_lookup.get(decor_id)
        if decor is not None:
            items.append(
                {
                    "kind": "decor",
                    "item_id": decor_id,
                    "name_snapshot": decor.get("name") or "Decor",
                    "price_paise": int(decor.get("price_paise", 0)),
                }
            )

    for combo_id in parse_id_list(row.get("combosselected")):
        combo = combo_lookup.get(combo_id)
        if combo is not None:
            items.append(
                {
                    "kind": "combo",
                    "item_id": combo_id,
                    "name_snapshot": combo.get("name") or "Combo",
                    "price_paise": int(combo.get("price_paise", 0)),
                }
            )

    return items


def build_payments(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive payments ledger rows from the old per-method advance columns.

    One row per method whose amount > 0. Method inference:
    upipayment / onlinepayment -> 'upi'; cashadvance -> 'cash'. All migrated
    rows carry provider=NULL, provider_ref=NULL, note='migrated', and
    received_at = createts.
    """
    received_at = to_utc_isoformat(row.get("createts"))
    sources = (
        ("upipayment", "upi"),
        ("cashadvance", "cash"),
        ("onlinepayment", "upi"),
    )
    payments: list[dict[str, Any]] = []
    for column, method in sources:
        amount_paise = rupees_to_paise(row.get(column))
        if amount_paise > 0:
            payments.append(
                {
                    "method": method,
                    "amount_paise": amount_paise,
                    "received_at": received_at,
                    "provider": None,
                    "provider_ref": None,
                    "note": "migrated",
                }
            )
    return payments


def transform_booking(
    row: dict[str, Any],
    *,
    used_references: set[str],
) -> dict[str, Any]:
    """Map an old `booking` row to a new `bookings` record (money x100, status map).

    Legacy decor booleans and couponcode are dropped. A unique public_token is
    generated. The old bookingreference is kept, but regenerated on collision
    against `used_references` (which the caller mutates to stay unique). The
    historical advance snapshot is max(advanceamount x100, 0).
    """
    total_paise = rupees_to_paise(row.get("amount"))
    reference = _unique_reference(row.get("bookingreference"), used_references)
    advance_snapshot = max(rupees_to_paise(row.get("advanceamount")), 0)
    return {
        "id": int(row["id"]),
        "booking_reference": reference,
        "public_token": generate_public_token(),
        "location_id": int(row["locationid"]),
        "plan_id": int(row["planid"]),
        "slot_id": int(row["slotid"]),
        "booking_date": to_utc_isoformat(row.get("date")),
        "booking_name": row.get("bookingname") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone"),
        "special_person_name": row.get("specialpersonname"),
        "name_on_cake": row.get("nameonthecake"),
        "message": row.get("message"),
        "people": parse_people(row.get("people")),
        "occasion_id": int(row["occasionid"]) if row.get("occasionid") else None,
        "plan_price_paise": total_paise,
        "subtotal_paise": total_paise,
        "discount_paise": rupees_to_paise(row.get("discount")),
        "food_paise": rupees_to_paise(row.get("foodamount")),
        "other_paise": rupees_to_paise(row.get("otheramount")),
        "cleaning_paise": rupees_to_paise(row.get("cleaningcharge")),
        "total_paise": total_paise,
        "advance_paise": advance_snapshot,
        "status": STATUS_MAP.get(int(row.get("statusid", 1)), "pending"),
        "crm_user_id": int(row["crm"]) if row.get("crm") else None,
        "created_at": to_utc_isoformat(row.get("createts")),
    }


def _unique_reference(reference: Any, used: set[str]) -> str:
    """Return a unique booking reference, regenerating on collision/absence."""
    candidate = str(reference).strip() if reference else ""
    if not candidate or candidate in used:
        base = candidate or "CC"
        while True:
            candidate = f"{base}-{secrets.token_hex(4).upper()}"
            if candidate not in used:
                break
    used.add(candidate)
    return candidate
