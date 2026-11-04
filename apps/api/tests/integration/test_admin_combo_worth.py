"""Admin control of combo worth/compare-at (real Postgres).

Combo catalog management is admin-only (router-level require_role("admin")).
These tests cover:
- an admin setting compare_at_paise on create and via PATCH, reflected in both
  the admin read and the public combos endpoint (worth_paise + savings_paise);
- server validation rejecting a negative worth (422);
- a non-admin (staff) user being forbidden (403) from the combo endpoints.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_combo, make_location, make_user

pytestmark = pytest.mark.integration

_ORIGIN = {"Origin": "http://localhost:5173"}


def _login(client: TestClient, username: str) -> None:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "pw-123456"},
        headers=_ORIGIN,
    )
    assert resp.status_code == 200


def test_admin_sets_worth_reflected_in_admin_and_public(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, "admin")

    # Create with worth above price -> positive saving.
    create = client.post(
        "/api/v1/admin/combos",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "name": "Combo-1",
            "description": "Fog + cake",
            "price_paise": 70000,
            "compare_at_paise": 100000,
            "effective_from": "2020-01-01",
        },
    )
    assert create.status_code == 201
    body = create.json()
    combo_id = body["id"]
    assert body["compare_at_paise"] == 100000
    assert body["savings_paise"] == 30000

    # Public endpoint reflects the same worth + saving.
    pub = client.get(f"/api/v1/public/locations/{loc.id}/combos")
    (pub_combo,) = pub.json()
    assert pub_combo["worth_paise"] == 100000
    assert pub_combo["savings_paise"] == 30000

    # PATCH the worth; public response recomputes savings.
    patch = client.patch(
        f"/api/v1/admin/combos/{combo_id}",
        headers=_ORIGIN,
        json={"compare_at_paise": 90000},
    )
    assert patch.status_code == 200
    assert patch.json()["savings_paise"] == 20000

    pub2 = client.get(f"/api/v1/public/locations/{loc.id}/combos")
    assert pub2.json()[0]["savings_paise"] == 20000


def test_negative_worth_rejected(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    make_user(db, "admin", location_id=None)
    db.commit()
    _login(client, "admin")

    resp = client.post(
        "/api/v1/admin/combos",
        headers=_ORIGIN,
        json={
            "location_id": loc.id,
            "name": "Combo-bad",
            "description": "x",
            "price_paise": 70000,
            "compare_at_paise": -1,
            "effective_from": "2020-01-01",
        },
    )
    assert resp.status_code == 422


def test_staff_forbidden_from_combo_worth(client: TestClient, db: Session) -> None:
    loc = make_location(db)
    combo = make_combo(db, loc.id, price_paise=70000)
    make_user(db, "staff", location_id=loc.id)
    db.commit()
    _login(client, "staff")

    resp = client.patch(
        f"/api/v1/admin/combos/{combo.id}",
        headers=_ORIGIN,
        json={"compare_at_paise": 100000},
    )
    assert resp.status_code == 403
