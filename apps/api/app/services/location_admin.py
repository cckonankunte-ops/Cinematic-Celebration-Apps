"""Admin disallowed-booking-time service (admin-only, per-location).

CRUD over a branch's disallowed time ranges. Validation (start < end, positive
optional duration) is enforced by the Pydantic schema before we reach here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.location_disallowed_time import LocationDisallowedTime
from app.schemas.location_admin import DisallowedTimeCreate, DisallowedTimeRead


def list_disallowed_times(
    db: Session, location_id: int
) -> list[LocationDisallowedTime]:
    return list(
        db.execute(
            select(LocationDisallowedTime)
            .where(LocationDisallowedTime.location_id == location_id)
            .order_by(LocationDisallowedTime.start_time)
        ).scalars()
    )


def create_disallowed_time(
    db: Session, location_id: int, data: DisallowedTimeCreate
) -> LocationDisallowedTime:
    row = LocationDisallowedTime(
        location_id=location_id,
        start_time=data.start_time,
        end_time=data.end_time,
        max_duration_minutes=data.max_duration_minutes,
        note=data.note,
        is_active=data.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_disallowed_time(db: Session, location_id: int, row_id: int) -> None:
    row = db.get(LocationDisallowedTime, row_id)
    if row is None or row.location_id != location_id:
        raise NotFoundError("Disallowed time not found.")
    db.delete(row)
    db.commit()


def to_disallowed_time_read(row: LocationDisallowedTime) -> DisallowedTimeRead:
    return DisallowedTimeRead(
        id=row.id,
        location_id=row.location_id,
        start_time=row.start_time,
        end_time=row.end_time,
        max_duration_minutes=row.max_duration_minutes,
        note=row.note,
        is_active=row.is_active,
    )
