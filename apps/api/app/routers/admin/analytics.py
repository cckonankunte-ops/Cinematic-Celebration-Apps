"""Admin analytics endpoints (admin ONLY).

Thin router over ``services.analytics``. The whole router is guarded by
``require_role("admin")`` (staff cannot see financial analytics) plus the
Origin check. Dates are an inclusive IST range (``date_from`` / ``date_to``);
a single legacy ``date`` param is accepted as a one-day range. ``status`` may be
repeated. Export endpoints stream a server-generated ``.xlsx``.
"""

from dataclasses import dataclass
from datetime import date as _date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import ValidationFailedError
from app.core.security import CurrentUser, check_origin, require_role
from app.schemas.analytics import (
    BookingStatusName,
    CreatedBookingsResult,
    SlotAmountsResult,
    TodayIncomeResult,
)
from app.services import analytics as analytics_service
from app.services import excel as excel_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-analytics"],
    dependencies=[Depends(require_role("admin")), Depends(check_origin)],
)

_XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@dataclass
class DateRange:
    date_from: _date
    date_to: _date

    @property
    def label(self) -> str:
        if self.date_from == self.date_to:
            return self.date_from.isoformat()
        return f"{self.date_from.isoformat()}_to_{self.date_to.isoformat()}"


def _date_range(
    date_from: _date | None = Query(default=None),
    date_to: _date | None = Query(default=None),
    on_date: _date | None = Query(default=None, alias="date"),
) -> DateRange:
    """Resolve the range; a lone ``date`` (legacy) or lone ``date_from`` = one day."""
    start = date_from or on_date
    if start is None:
        raise ValidationFailedError("Provide date_from (and optionally date_to).")
    return DateRange(start, date_to or start)


def _xlsx_response(buffer: object, filename: str) -> StreamingResponse:
    """Wrap an in-memory ``.xlsx`` buffer as an attachment download."""
    return StreamingResponse(
        buffer,  # type: ignore[arg-type]
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Bookings reports default to accepted only; money-received includes every status.
_BOOKING_STATUSES = Query(default=["accepted"], alias="status")
_ANY_STATUS = Query(default=[], alias="status")


@router.get("/analytics/slot-amounts", response_model=SlotAmountsResult)
def get_slot_amounts(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _BOOKING_STATUSES,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> SlotAmountsResult:
    return analytics_service.slot_amounts(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )


@router.get("/analytics/created-bookings", response_model=CreatedBookingsResult)
def get_created_bookings(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _BOOKING_STATUSES,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> CreatedBookingsResult:
    return analytics_service.created_bookings(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )


@router.get("/analytics/today-income", response_model=TodayIncomeResult)
def get_today_income(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _ANY_STATUS,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> TodayIncomeResult:
    return analytics_service.today_income(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )


@router.get("/analytics/slot-amounts/export")
def export_slot_amounts(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _BOOKING_STATUSES,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> StreamingResponse:
    result = analytics_service.slot_amounts(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )
    buffer = excel_service.build_slot_amounts_xlsx(result)
    return _xlsx_response(buffer, f"slot-amounts-{rng.label}.xlsx")


@router.get("/analytics/created-bookings/export")
def export_created_bookings(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _BOOKING_STATUSES,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> StreamingResponse:
    result = analytics_service.created_bookings(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )
    buffer = excel_service.build_created_bookings_xlsx(result)
    return _xlsx_response(buffer, f"created-bookings-{rng.label}.xlsx")


@router.get("/analytics/today-income/export")
def export_today_income(
    location_id: int,
    rng: DateRange = Depends(_date_range),
    statuses: list[BookingStatusName] = _ANY_STATUS,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> StreamingResponse:
    result = analytics_service.today_income(
        db, actor, location_id=location_id,
        date_from=rng.date_from, date_to=rng.date_to, statuses=statuses,
    )
    buffer = excel_service.build_today_income_xlsx(result)
    return _xlsx_response(buffer, f"income-{rng.label}.xlsx")
