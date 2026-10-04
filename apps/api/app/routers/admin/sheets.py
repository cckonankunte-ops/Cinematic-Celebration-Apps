"""Admin operational-sheet endpoints (admin + staff).

Thin router over ``services.sheets``. Location access is enforced in the
service layer so staff are limited to their assigned location. The ``date``
query param is aliased to avoid shadowing ``datetime.date``. Export endpoints
stream a server-generated ``.xlsx`` (openpyxl) as an attachment.
"""

from datetime import date as _date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import CurrentUser, check_origin, require_role
from app.schemas.sheets import CakesheetRow, TimesheetRow
from app.services import excel as excel_service
from app.services import sheets as sheets_service

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-sheets"],
    dependencies=[Depends(require_role("admin", "staff")), Depends(check_origin)],
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


@router.get("/timesheet", response_model=list[TimesheetRow])
def get_timesheet(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> list[TimesheetRow]:
    return sheets_service.timesheet(db, actor, location_id=location_id, on_date=on_date)


@router.get("/cakesheet", response_model=list[CakesheetRow])
def get_cakesheet(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> list[CakesheetRow]:
    return sheets_service.cakesheet(db, actor, location_id=location_id, on_date=on_date)


@router.get("/timesheet/export")
def export_timesheet(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> StreamingResponse:
    rows = sheets_service.timesheet(db, actor, location_id=location_id, on_date=on_date)
    buffer = excel_service.build_timesheet_xlsx(rows)
    return _xlsx_response(buffer, f"timesheet-{on_date.isoformat()}.xlsx")


@router.get("/cakesheet/export")
def export_cakesheet(
    location_id: int,
    on_date: _date = Query(alias="date"),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin", "staff")),
) -> StreamingResponse:
    rows = sheets_service.cakesheet(db, actor, location_id=location_id, on_date=on_date)
    buffer = excel_service.build_cakesheet_xlsx(rows)
    return _xlsx_response(buffer, f"cakesheet-{on_date.isoformat()}.xlsx")
