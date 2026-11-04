"""Public combos endpoint: server-provided worth + savings (real Postgres).

GET /api/v1/public/locations/{id}/combos must return worth_paise and a derived
savings_paise = max(0, worth - price), computed server-side. A combo with no
cake/LED baseline and no worth must still return a valid, zero-savings payload.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.factories import make_combo, make_location

pytestmark = pytest.mark.integration


def test_public_combos_return_worth_and_savings(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    # Worth above price -> positive saving.
    make_combo(db, loc.id, price_paise=70000, compare_at_paise=100000)
    # Worth below price -> zero saving (never negative).
    make_combo(db, loc.id, price_paise=70000, compare_at_paise=50000)
    # No worth configured -> zero saving, worth_paise null.
    make_combo(db, loc.id, price_paise=70000)
    db.commit()

    resp = client.get(f"/api/v1/public/locations/{loc.id}/combos")
    assert resp.status_code == 200
    combos = resp.json()
    assert len(combos) == 3

    by_savings = sorted(combos, key=lambda c: c["savings_paise"])
    # Two zero-savings combos and one with 30000 saving.
    assert by_savings[0]["savings_paise"] == 0
    assert by_savings[1]["savings_paise"] == 0
    assert by_savings[2]["savings_paise"] == 30000
    assert by_savings[2]["worth_paise"] == 100000

    # The unset-worth combo surfaces worth_paise as null and savings 0.
    unset = next(c for c in combos if c["worth_paise"] is None)
    assert unset["savings_paise"] == 0


def test_no_baseline_combo_renders_valid_payload(
    client: TestClient, db: Session
) -> None:
    loc = make_location(db)
    # No cake/LED baseline and no worth: must still return a complete record.
    make_combo(db, loc.id, price_paise=40000)
    db.commit()

    resp = client.get(f"/api/v1/public/locations/{loc.id}/combos")
    assert resp.status_code == 200
    (combo,) = resp.json()
    assert combo["price_paise"] == 40000
    assert combo["worth_paise"] is None
    assert combo["savings_paise"] == 0
    assert combo["image_url"]  # non-empty public URL
    assert "name" in combo and "description" in combo
