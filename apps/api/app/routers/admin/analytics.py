"""Admin analytics endpoints (admin ONLY).

Thin router over ``services.analytics``. The whole router is guarded by
``require_role("admin")`` (staff cannot see financial analytics) plus the
Origin check. The ``date`` query param is aliased to avoid shadowing
``datetime.date``. Export endpoints stream a server-generated ``.xlsx``.
"""

from __future__ import annotations

from datetime import date as _date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, check_origin, require_role
from app.schemas.analytics import AdvanceAmountsResult, SlotAmountsResult
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


def _xlsx_response(buffer: object, filename: str) -> StreamingResponse:
    """Wrap an in-memory ``.xlsx`` buffer as an attachment download."""
    return StreamingResponse(
        buffer,  # type: ignore[arg-type]
        media_type=_XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analytics/slot-amounts", response_model=SlotAmountsResult)
def get_slot_amounts(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> SlotAmountsResult:
    return analytics_service.slot_amounts(
        db, actor, location_id=location_id, on_date=on_date
    )


@router.get("/analytics/advance-amounts", response_model=AdvanceAmountsResult)
def get_advance_amounts(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> AdvanceAmountsResult:
    return analytics_service.advance_amounts(
        db, actor, location_id=location_id, on_date=on_date
    )


@router.get("/analytics/slot-amounts/export")
def export_slot_amounts(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> StreamingResponse:
    result = analytics_service.slot_amounts(
        db, actor, location_id=location_id, on_date=on_date
    )
    buffer = excel_service.build_slot_amounts_xlsx(result)
    return _xlsx_response(buffer, f"slot-amounts-{on_date.isoformat()}.xlsx")


@router.get("/analytics/advance-amounts/export")
def export_advance_amounts(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> StreamingResponse:
    result = analytics_service.advance_amounts(
        db, actor, location_id=location_id, on_date=on_date
    )
    buffer = excel_service.build_advance_amounts_xlsx(result)
    return _xlsx_response(buffer, f"advance-amounts-{on_date.isoformat()}.xlsx")
