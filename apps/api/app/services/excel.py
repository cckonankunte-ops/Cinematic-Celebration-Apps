"""Server-side ``.xlsx`` builders for operational sheets and analytics.

Workbooks are generated with openpyxl and returned as an in-memory
``BytesIO`` ready to stream (no client-side spreadsheet libraries, per
tech.md). Human-facing money columns are shown in **rupees** (paise / 100) and
their headers are suffixed ``(Rs.)``; the raw ledger stays in paise elsewhere.

Each builder takes already-assembled rows (from ``services.sheets`` /
``services.analytics``) plus a column spec, so this module holds no business
logic â€” only presentation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.schemas.analytics import (
    CreatedBookingsResult,
    SlotAmountsResult,
    TodayIncomeResult,
)
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


_METHOD_ORDER = ("cash", "upi", "card", "other")
_IST = ZoneInfo("Asia/Kolkata")


def _method_label(method: str) -> str:
    return method.upper() if method == "upi" else method.capitalize()


def _method_order(per_row: Sequence[dict[str, int]], totals: dict[str, int]) -> list[str]:
    """Known methods first (cash, upi, card, other), then any new ones sorted."""
    seen: set[str] = set(totals)
    for methods in per_row:
        seen.update(methods)
    known = [m for m in _METHOD_ORDER if m in seen]
    return known + sorted(seen - set(_METHOD_ORDER))


def build_slot_amounts_xlsx(result: SlotAmountsResult) -> BytesIO:
    """Slot-amounts workbook: one row per booking + a Summary footer row."""
    methods = _method_order(
        [r.paid_by_method for r in result.rows], result.summary.paid_by_method
    )
    columns: list[Column] = [
        ("Reference", lambda r: r.booking_reference),
        ("Name", lambda r: r.booking_name),
        ("Celebration Date", lambda r: r.booking_date.isoformat()),
        ("Status", lambda r: r.status),
        ("Total (Rs.)", lambda r: _rupees(r.total_paise)),
        ("Paid (Rs.)", lambda r: _rupees(r.amount_paid_paise)),
        *[
            (f"{_method_label(m)} (Rs.)", lambda r, m=m: _rupees(r.paid_by_method.get(m, 0)))
            for m in methods
        ],
        ("Due (Rs.)", lambda r: _rupees(r.amount_due_paise)),
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
            f"Summary ({s.booking_count} bookings)",
            "",
            "",
            "",
            _rupees(s.total_paise),
            _rupees(s.amount_paid_paise),
            *[_rupees(s.paid_by_method.get(m, 0)) for m in methods],
            _rupees(s.amount_due_paise),
            _rupees(s.discount_paise),
            _rupees(s.food_paise),
            _rupees(s.cleaning_paise),
            _rupees(s.other_paise),
        ]
    )
    return _finalize(wb)


def build_created_bookings_xlsx(result: CreatedBookingsResult) -> BytesIO:
    """Bookings-created workbook with a Summary footer row."""
    columns: list[Column] = [
        ("Reference", lambda r: r.booking_reference),
        ("Name", lambda r: r.booking_name),
        ("Created At", lambda r: r.created_at.astimezone(_IST).strftime("%Y-%m-%d %H:%M")),
        ("Celebration Date", lambda r: r.booking_date.isoformat()),
        ("Status", lambda r: r.status),
        ("Plan", lambda r: r.plan_title),
        ("Cake", lambda r: r.cake or ""),
        ("Special Decor", lambda r: ", ".join(r.special_decor)),
        ("Combos", lambda r: ", ".join(r.combos)),
        ("Total (Rs.)", lambda r: _rupees(r.total_paise)),
        ("Paid (Rs.)", lambda r: _rupees(r.amount_paid_paise)),
        ("Due (Rs.)", lambda r: _rupees(r.amount_due_paise)),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Bookings Created"
    _write_sheet(ws, columns, result.rows)
    s = result.summary
    ws.append(
        [f"Summary ({s.booking_count} bookings)"]
        + [""] * 8
        + [_rupees(s.total_paise), _rupees(s.amount_paid_paise), _rupees(s.amount_due_paise)]
    )
    return _finalize(wb)


def build_today_income_xlsx(result: TodayIncomeResult) -> BytesIO:
    """Income-received workbook (per method) with a Summary footer row."""
    methods = _method_order(
        [r.received_by_method for r in result.rows], result.summary.received_by_method
    )
    columns: list[Column] = [
        ("Reference", lambda r: r.booking_reference),
        ("Name", lambda r: r.booking_name),
        ("Celebration Date", lambda r: r.booking_date.isoformat()),
        ("Status", lambda r: r.status),
        ("Received (Rs.)", lambda r: _rupees(r.received_paise)),
        *[
            (f"{_method_label(m)} (Rs.)", lambda r, m=m: _rupees(r.received_by_method.get(m, 0)))
            for m in methods
        ],
        ("Total (Rs.)", lambda r: _rupees(r.total_paise)),
        ("Paid To Date (Rs.)", lambda r: _rupees(r.amount_paid_paise)),
        ("Due (Rs.)", lambda r: _rupees(r.amount_due_paise)),
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Income"
    _write_sheet(ws, columns, result.rows)
    s = result.summary
    ws.append(
        [f"Summary ({s.booking_count} bookings)", "", "", "", _rupees(s.received_paise)]
        + [_rupees(s.received_by_method.get(m, 0)) for m in methods]
    )
    return _finalize(wb)