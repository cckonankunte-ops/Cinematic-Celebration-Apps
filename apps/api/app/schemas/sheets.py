"""Operational sheet schemas (timesheet, cakesheet).

Read-only rows assembled by ``services.sheets``. Money stays in integer paise;
the UI converts to rupees for display. ``slot_sort_order`` + ``slot_description``
let the UI group rows by slot without a second query.
"""

from __future__ import annotations

from pydantic import BaseModel


class TimesheetRow(BaseModel):
    slot_id: int
    slot_sort_order: int
    slot_description: str
    plan_title: str
    booking_name: str
    phone: str | None
    people: int
    name_on_cake: str | None
    cake: str | None
    special_decor: str | None
    combos: str | None
    occasion: str | None
    amount_due_paise: int


class CakesheetRow(BaseModel):
    slot_id: int
    slot_sort_order: int
    slot_description: str
    cake: str
    name_on_cake: str | None
