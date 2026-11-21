"""Unit tests for the ``.xlsx`` export builders (pure, no DB).

Build a workbook from a couple of rows, load it back from the ``BytesIO`` with
openpyxl, and assert the header row plus a Day Summary footer where expected.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from openpyxl import load_workbook

from app.schemas.analytics import (
    AnalyticsSummary,
    CreatedBookingRow,
    CreatedBookingsResult,
    SlotAmountRow,
    SlotAmountsResult,
    TodayIncomeResult,
    TodayIncomeRow,
    TodayIncomeSummary,
)
from app.schemas.sheets import CakesheetRow, TimesheetRow
from app.services import excel as excel_service

_NOW = datetime(2025, 1, 1, 10, 30, tzinfo=UTC)


def _timesheet_rows() -> list[TimesheetRow]:
    return [
        TimesheetRow(
            slot_id=1,
            slot_sort_order=1,
            slot_description="9 AM - 12 PM",
            plan_title="Starlight",
            booking_name="Priya",
            phone="9876543210",
            people=6,
            name_on_cake="Happy Birthday",
            cake="Chocolate truffle",
            special_decor="Rose bouquet",
            combos="Party combo",
            occasion="Birthday - Ravi",
            amount_due_paise=400000,
        )
    ]


def test_timesheet_xlsx_has_header_and_rows() -> None:
    buffer = excel_service.build_timesheet_xlsx(_timesheet_rows())
    wb = load_workbook(buffer)
    ws = wb.active
    header = [cell.value for cell in ws[1]]
    assert header[0] == "Slot"
    assert "Amount Due (Rs.)" in header
    # One header row + one data row.
    assert ws.max_row == 2
    # Money column is shown in rupees (paise / 100).
    assert ws.cell(row=2, column=header.index("Amount Due (Rs.)") + 1).value == 4000.0


def test_cakesheet_xlsx_structure() -> None:
    rows = [
        CakesheetRow(
            slot_id=1,
            slot_sort_order=1,
            slot_description="9 AM - 12 PM",
            cake="Chocolate truffle",
            name_on_cake="Happy Birthday",
        )
    ]
    buffer = excel_service.build_cakesheet_xlsx(rows)
    wb = load_workbook(buffer)
    ws = wb.active
    header = [cell.value for cell in ws[1]]
    assert header == ["Slot", "Cake", "Name on Cake"]
    assert ws.max_row == 2


def _summary(**over) -> AnalyticsSummary:
    base = dict(
        booking_count=1,
        total_paise=400000,
        amount_paid_paise=50000,
        amount_due_paise=350000,
        discount_paise=0,
        food_paise=0,
        cleaning_paise=0,
        other_paise=0,
        paid_by_method={"upi": 30000, "cash": 20000},
    )
    base.update(over)
    return AnalyticsSummary(**base)


def test_slot_amounts_xlsx_has_method_columns_and_summary() -> None:
    result = SlotAmountsResult(
        rows=[
            SlotAmountRow(
                booking_name="Priya",
                booking_reference="CC-ABC",
                booking_date=date(2025, 1, 5),
                status="accepted",
                total_paise=400000,
                amount_paid_paise=50000,
                paid_by_method={"upi": 30000, "cash": 20000},
                amount_due_paise=350000,
                discount_paise=0,
                food_paise=0,
                cleaning_paise=0,
                other_paise=0,
            )
        ],
        summary=_summary(),
    )
    ws = load_workbook(excel_service.build_slot_amounts_xlsx(result)).active
    header = [c.value for c in ws[1]]
    # Known methods come in a fixed order: cash before upi.
    assert header.index("Cash (Rs.)") < header.index("UPI (Rs.)")
    assert ws.max_row == 3  # header + row + summary
    assert str(ws.cell(row=3, column=1).value).startswith("Summary")
    assert ws.cell(row=2, column=header.index("UPI (Rs.)") + 1).value == 300.0


def test_slot_amounts_xlsx_includes_new_payment_method() -> None:
    result = SlotAmountsResult(
        rows=[],
        summary=_summary(paid_by_method={"cash": 100, "wallet": 200}),
    )
    ws = load_workbook(excel_service.build_slot_amounts_xlsx(result)).active
    header = [c.value for c in ws[1]]
    assert "Wallet (Rs.)" in header


def test_created_bookings_xlsx_lists_addons() -> None:
    result = CreatedBookingsResult(
        rows=[
            CreatedBookingRow(
                booking_name="Priya",
                booking_reference="CC-ABC",
                created_at=_NOW,
                booking_date=date(2025, 1, 5),
                status="accepted",
                plan_title="Platinum",
                cake="Truffle (1 kg)",
                special_decor=["Balloons ×2", "Fog"],
                combos=["Snacks"],
                total_paise=400000,
                amount_paid_paise=50000,
                amount_due_paise=350000,
            )
        ],
        summary=_summary(),
    )
    ws = load_workbook(excel_service.build_created_bookings_xlsx(result)).active
    header = [c.value for c in ws[1]]
    assert ws.cell(row=2, column=header.index("Special Decor") + 1).value == "Balloons ×2, Fog"
    assert ws.max_row == 3


def test_today_income_xlsx_per_method() -> None:
    result = TodayIncomeResult(
        rows=[
            TodayIncomeRow(
                booking_name="Priya",
                booking_reference="CC-ABC",
                booking_date=date(2025, 1, 5),
                status="accepted",
                received_paise=50000,
                received_by_method={"upi": 50000},
                total_paise=400000,
                amount_paid_paise=50000,
                amount_due_paise=350000,
            )
        ],
        summary=TodayIncomeSummary(
            booking_count=1,
            payment_count=1,
            received_paise=50000,
            received_by_method={"upi": 50000},
        ),
    )
    ws = load_workbook(excel_service.build_today_income_xlsx(result)).active
    header = [c.value for c in ws[1]]
    assert "UPI (Rs.)" in header
    assert ws.max_row == 3
    assert ws.cell(row=3, column=5).value == 500.0