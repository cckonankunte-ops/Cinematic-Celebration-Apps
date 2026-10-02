"""Unit tests for the PURE transform helpers.

These tests have NO external dependencies (no DB, no network, no pymysql/
boto3/psycopg) so they run anywhere. The transform module is loaded directly
from its file path so the test suite does not depend on how the standalone
migration package is placed on sys.path.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

_PKG_DIR = Path(__file__).resolve().parent.parent


def _load(module_name: str, filename: str) -> ModuleType:
    """Load a sibling migration module by file path under a package alias."""
    # Register a lightweight package so transform.py's relative imports resolve.
    pkg_name = "migrate_pkg_under_test"
    if pkg_name not in sys.modules:
        pkg = ModuleType(pkg_name)
        pkg.__path__ = [str(_PKG_DIR)]  # type: ignore[attr-defined]
        sys.modules[pkg_name] = pkg
    full = f"{pkg_name}.{module_name}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, _PKG_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


# Load config first so transform's "from .config import ..." resolves.
_load("config", "config.py")
T = _load("transform", "transform.py")


# -- rupees_to_paise --------------------------------------------------------


def test_rupees_to_paise_basic() -> None:
    assert T.rupees_to_paise(500) == 50000
    assert T.rupees_to_paise("150") == 15000
    assert T.rupees_to_paise(0) == 0


def test_rupees_to_paise_handles_none_and_garbage() -> None:
    assert T.rupees_to_paise(None) == 0
    assert T.rupees_to_paise("") == 0
    assert T.rupees_to_paise("abc") == 0


def test_rupees_to_paise_rounds_floats() -> None:
    assert T.rupees_to_paise(1.005) == 100  # 100.5 -> round to 100 (banker's)
    assert T.rupees_to_paise(2.5) == 250


# -- slugify ----------------------------------------------------------------


def test_slugify_lowercases_and_hyphenates() -> None:
    assert T.slugify("Electronic City") == "electronic-city"
    assert T.slugify("Hulimavu") == "hulimavu"


def test_slugify_strips_non_alnum_and_edges() -> None:
    assert T.slugify("  Konankunte!! ") == "konankunte"
    assert T.slugify("A & B / C") == "a-b-c"


# -- status map -------------------------------------------------------------


def test_status_map_values() -> None:
    assert T.STATUS_MAP[1] == "pending"
    assert T.STATUS_MAP[2] == "accepted"
    assert T.STATUS_MAP[3] == "rejected"


def test_status_to_is_active() -> None:
    assert T.status_to_is_active(1) is True
    assert T.status_to_is_active(0) is False
    assert T.status_to_is_active(None) is False


# -- people parse -----------------------------------------------------------


def test_parse_people_valid_and_fallback() -> None:
    assert T.parse_people("6") == 6
    assert T.parse_people(4) == 4
    assert T.parse_people("not a number") == 1
    assert T.parse_people(None) == 1
    assert T.parse_people("0") == 1  # minimum of 1


# -- cakeid sentinel --------------------------------------------------------


def test_is_real_cake_sentinel_is_no_cake() -> None:
    assert T.is_real_cake(1) is False  # sentinel "no cake"
    assert T.is_real_cake(0) is False
    assert T.is_real_cake(None) is False
    assert T.is_real_cake(5) is True


def test_build_booking_items_omits_sentinel_cake() -> None:
    cakes = {5: {"description": "Chocolate", "price_paise": 60000}}
    sentinel = T.build_booking_items(
        {"cakeid": 1}, cake_lookup=cakes, decor_lookup={}, combo_lookup={}
    )
    assert sentinel == []
    real = T.build_booking_items(
        {"cakeid": 5}, cake_lookup=cakes, decor_lookup={}, combo_lookup={}
    )
    assert real == [
        {"kind": "cake", "item_id": 5, "name_snapshot": "Chocolate", "price_paise": 60000}
    ]


# -- JSON array parsing -----------------------------------------------------


def test_parse_id_list_variants() -> None:
    assert T.parse_id_list("[1, 3]") == [1, 3]
    assert T.parse_id_list("1,2,3") == [1, 2, 3]
    assert T.parse_id_list([4, 5]) == [4, 5]
    assert T.parse_id_list(None) == []
    assert T.parse_id_list("") == []
    assert T.parse_id_list("[]") == []


def test_build_booking_items_decor_and_combo_snapshots() -> None:
    decor = {1: {"name": "Balloons", "price_paise": 20000}}
    combos = {2: {"name": "Snack Combo", "price_paise": 30000}}
    items = T.build_booking_items(
        {"specialdecorselected": "[1]", "combosselected": "[2]"},
        cake_lookup={},
        decor_lookup=decor,
        combo_lookup=combos,
    )
    kinds = {i["kind"]: i for i in items}
    assert kinds["decor"]["price_paise"] == 20000
    assert kinds["combo"]["name_snapshot"] == "Snack Combo"


# -- payment-row derivation -------------------------------------------------


def test_build_payments_one_row_per_positive_method() -> None:
    row = {
        "upipayment": 300,
        "cashadvance": 200,
        "onlinepayment": 0,
        "createts": "2024-01-01T10:00:00+00:00",
    }
    payments = T.build_payments(row)
    assert len(payments) == 2
    methods = {p["method"]: p["amount_paise"] for p in payments}
    assert methods == {"upi": 30000, "cash": 20000}
    assert all(p["provider"] is None and p["note"] == "migrated" for p in payments)


def test_build_payments_empty_when_all_zero() -> None:
    assert T.build_payments({"upipayment": 0, "cashadvance": 0, "onlinepayment": 0}) == []


# -- booking transform ------------------------------------------------------


def test_transform_booking_core_mappings() -> None:
    used: set[str] = set()
    row = {
        "id": 10,
        "bookingreference": "CC-ABC-123",
        "locationid": 1,
        "planid": 2,
        "slotid": 3,
        "date": "2025-12-25",
        "bookingname": "Priya",
        "email": "p@example.com",
        "people": "6",
        "amount": 4500,
        "advanceamount": 500,
        "discount": 100,
        "statusid": 2,
        "couponcode": "DROPME",
        "tabledecor": 1,
        "createts": datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
    }
    out = T.transform_booking(row, used_references=used)
    assert out["status"] == "accepted"
    assert out["total_paise"] == 450000
    assert out["advance_paise"] == 50000
    assert out["discount_paise"] == 10000
    assert out["people"] == 6
    assert out["booking_reference"] == "CC-ABC-123"
    assert len(out["public_token"]) >= 16
    # legacy decor booleans and couponcode must be dropped
    assert "couponcode" not in out
    assert "tabledecor" not in out


def test_transform_booking_regenerates_duplicate_reference() -> None:
    used = {"CC-DUP"}
    out = T.transform_booking(
        {
            "id": 1, "bookingreference": "CC-DUP", "locationid": 1, "planid": 1,
            "slotid": 1, "date": "2025-01-01", "amount": 0, "statusid": 1,
        },
        used_references=used,
    )
    assert out["booking_reference"] != "CC-DUP"
    assert out["booking_reference"] in used


# -- location transform -----------------------------------------------------


def test_transform_location_derives_slug_and_is_active() -> None:
    out = T.transform_location(
        {"id": 1, "name": "Electronic City", "status": 1, "address": "x", "phone": "9"}
    )
    assert out["slug"] == "electronic-city"
    assert out["is_active"] is True


# -- plan transform (DECIDE constants) --------------------------------------


def test_transform_plan_applies_decided_constants() -> None:
    out = T.transform_plan(
        {
            "id": 1, "locationid": 1, "title": "Starlight", "plantype": 2,
            "amount": 2500, "peopleallowed": 4, "maxpeopleallowed": 10,
            "givediscount": 1, "maxdiscount": 300,
        }
    )
    assert out["price_paise"] == 250000
    assert out["extra_guest_paise"] == 15000
    assert out["advance_paise"] == 50000
    assert out["max_discount_paise"] == 30000
    assert out["give_discount"] is True


# -- user transform (password safety) ---------------------------------------


def test_transform_user_never_copies_plaintext_password() -> None:
    out = T.transform_user(
        {"id": 1, "username": "staff1", "password": "plain123", "locationid": 2},
        role_name="staff",
        password_hash="$argon2id$fake$hash",
    )
    assert out["password_hash"] == "$argon2id$fake$hash"
    assert out["must_reset_password"] is True
    assert "password" not in out
    assert out["location_id"] == 2


def test_transform_user_admin_location_null() -> None:
    out = T.transform_user(
        {"id": 1, "username": "admin", "password": "x", "locationid": 0},
        role_name="admin",
        password_hash="h",
    )
    assert out["location_id"] is None
