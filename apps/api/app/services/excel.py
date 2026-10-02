"""Server-side ``.xlsx`` builders for operational sheets and analytics.

Workbooks are generated with openpyxl and returned as an in-memory
``BytesIO`` ready to stream (no client-side spreadsheet libraries, per
tech.md). Human-facing money columns are shown in **rupees** (paise / 100) and
their headers are suffixed ``(Rs.)``; the raw ledger stays in paise elsewhere.

Each builder takes already-assembled rows (from ``services.sheets`` /
``services.analytics``) plus a column spec, so this module holds no business
logic — only presentation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas.analytics import AdvanceAmountsResult, SlotAmountsResult
from app.schemas.sheets import CakesheetRow, TimesheetRow

# A column spec entry: (header, accessor). The accessor pulls a display value
# from a row object.
Column = tuple[str, Callable[[Any], Any]]


def _rupees(paise: int | None) -> float:
    """Convert integer paise to a rupee float for display cells."""
    return round((paise or 0) / 100, 2)


def _write_sheet(ws: Worksheet, columns: Sequence[Column], rows: Sequence[Any]) -> None:
    """Write a header row followed by one data row per item."""
    ws.append([header for header, _ in columns])
    for row in rows:
        ws.append([accessor(row) for _, accessor in columns])


def _finalize(wb: Workbook) -> BytesIO:
    """Save a workbook to a rewound ``BytesIO`` for streaming."""
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def build_timesheet_xlsx(rows: Sequence[TimesheetRow]) -> BytesIO:
    """Build a time-sheet workbook (one row per accepted booking)."""
    columns: list[Column] = [
        ("Slot", lambda r: r.slot_description),
        ("Plan", lambda r: r.plan_title),
        ("Booking Name", lambda r: r.booking_name),
        ("Phone", lambda r: r.phone or ""),
        ("People", lambda r: r.people),
        ("Name on Cake", lambda r: r.name_on_cake or ""),
        ("Cake", lambda r: r.cake or ""),
        ("Special Decor", lambda r: r.special_decor or ""),
        ("Combos", lambda r: r.combos or ""),
        ("Occasion", lambda r: r.occasion or ""),
        ("Amount Due (Rs.)", lambda r: _rupees(r.amount_due_paise)),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Time Sheet"
    _write_sheet(ws, columns, rows)
    return _finalize(wb)


def build_cakesheet_xlsx(rows: Sequence[CakesheetRow]) -> BytesIO:
    """Build a cake-sheet workbook (one row per cake order)."""
    columns: list[Column] = [
        ("Slot", lambda r: r.slot_description),
        ("Cake", lambda r: r.cake),
        ("Name on Cake", lambda r: r.name_on_cake or ""),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Cake Sheet"
    _write_sheet(ws, columns, rows)
    return _finalize(wb)


def build_slot_amounts_xlsx(result: SlotAmountsResult) -> BytesIO:
    """Build a slot-amounts workbook with a Day Summary footer row."""
    columns: list[Column] = [
        ("Booking Name", lambda r: r.booking_name),
        ("Reference", lambda r: r.booking_reference),
        ("Total (Rs.)", lambda r: _rupees(r.total_paise)),
        ("Paid (Rs.)", lambda r: _rupees(r.amount_paid_paise)),
        ("Today Income (Rs.)", lambda r: _rupees(r.today_income_paise)),
        ("Amount Due (Rs.)", lambda r: _rupees(r.amount_due_paise)),
        ("Discount (Rs.)", lambda r: _rupees(r.discount_paise)),
        ("Food (Rs.)", lambda r: _rupees(r.food_paise)),
        ("Cleaning (Rs.)", lambda r: _rupees(r.cleaning_paise)),
        ("Other (Rs.)", lambda r: _rupees(r.other_paise)),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Slot Amounts"
    _write_sheet(ws, columns, result.rows)
    s = result.summary
    ws.append(
        [
            "Day Summary",
            "",
            _rupees(s.total_paise),
            _rupees(s.amount_paid_paise),
            _rupees(s.amount_paid_paise),
            _rupees(s.amount_due_paise),
            _rupees(s.discount_paise),
            _rupees(s.food_paise),
            _rupees(s.cleaning_paise),
            _rupees(s.other_paise),
        ]
    )
    return _finalize(wb)


def build_advance_amounts_xlsx(result: AdvanceAmountsResult) -> BytesIO:
    """Build an advance-amounts workbook with a Day Summary footer row."""
    columns: list[Column] = [
        ("Booking Name", lambda r: r.booking_name),
        ("Reference", lambda r: r.booking_reference),
        ("Total (Rs.)", lambda r: _rupees(r.total_paise)),
        ("Paid (Rs.)", lambda r: _rupees(r.amount_paid_paise)),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Advance Amounts"
    _write_sheet(ws, columns, result.rows)
    s = result.summary
    ws.append(
        [
            "Day Summary",
            "",
            _rupees(s.total_paise),
            _rupees(s.amount_paid_paise),
        ]
    )
    return _finalize(wb)
