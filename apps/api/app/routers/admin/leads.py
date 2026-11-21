"""Admin lead CRM endpoints (lead-crm R4, R5, R7, R10-R13, R18.8).

Router-level ``require_role(*LEAD_ACCESS)`` plus the Origin check: only admins
and receptionists may use the lead CRM (staff get 403), and every lead endpoint
needs a session (R12.1, R12.7). Branch access is enforced in
``services/leads.py`` (R12.2, R12.3). The dashboard is admin-only on top of
that (R12.5). Thin router: parse, call one service function, return a schema.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import LEAD_ACCESS, CurrentUser, check_origin, require_role
from app.schemas.lead import (
    ActivityCreate,
    AssignableUser,
    FollowUpDigest,
    LeadCounts,
    LeadCreate,
    LeadCreateResult,
    LeadDashboard,
    LeadListPage,
    LeadRead,
    LeadUpdate,
    LinkCodeIn,
)
from app.services import leads as leads_service
from app.services.slots import today_ist

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-leads"],
    dependencies=[Depends(require_role(*LEAD_ACCESS)), Depends(check_origin)],
)

_any_user = require_role(*LEAD_ACCESS)

DASHBOARD_DEFAULT_DAYS = 30


def _filters(
    location_id: int | None = None,
    statuses: list[str] = Query(default=[], alias="status"),
    sources: list[str] = Query(default=[], alias="source"),
    channels: list[str] = Query(default=[], alias="channel"),
    assigned_user_id: int | None = None,
    follow_from: date | None = None,
    follow_to: date | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> leads_service.LeadListFilters:
    return leads_service.LeadListFilters(
        location_id=location_id,
        statuses=tuple(statuses),
        sources=tuple(sources),
        channels=tuple(channels),
        assigned_user_id=assigned_user_id,
        follow_from=follow_from,
        follow_to=follow_to,
        created_from=created_from,
        created_to=created_to,
        q=q.strip() if q and q.strip() else None,
        limit=limit,
        offset=offset,
    )


@router.get("/leads", response_model=LeadListPage)
def list_leads(
    filters: leads_service.LeadListFilters = Depends(_filters),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadListPage:
    return leads_service.list_leads(db, actor, filters)


@router.get("/leads/counts", response_model=LeadCounts)
def get_lead_counts(
    location_id: int | None = None,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadCounts:
    return leads_service.lead_counts(db, actor, location_id)


@router.get("/leads/follow-ups", response_model=FollowUpDigest)
def get_follow_ups(
    location_id: int | None = None,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> FollowUpDigest:
    return leads_service.follow_up_digest(db, actor, location_id)


@router.get("/leads/assignable-users", response_model=list[AssignableUser])
def get_assignable_users(
    location_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> list[AssignableUser]:
    return leads_service.assignable_users(db, actor, location_id)


@router.get("/leads/dashboard", response_model=LeadDashboard)
def get_lead_dashboard(
    location_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_role("admin")),
) -> LeadDashboard:
    """Admin only (R12.5). Defaults to the last 30 days in IST (R13.1)."""
    end = date_to or today_ist()
    start = date_from or end - timedelta(days=DASHBOARD_DEFAULT_DAYS - 1)
    return leads_service.dashboard(
        db, actor, location_id=location_id, date_from=start, date_to=end
    )


@router.post("/leads", response_model=LeadCreateResult, status_code=status.HTTP_201_CREATED)
def create_lead(
    body: LeadCreate = Body(...),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadCreateResult:
    return leads_service.create_lead_read(db, body, actor)


@router.get("/leads/{lead_id}", response_model=LeadRead)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadRead:
    return leads_service.get_lead(db, lead_id, actor)


@router.patch("/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: int,
    body: LeadUpdate = Body(...),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadRead:
    return leads_service.update_lead_read(db, lead_id, body, actor)


@router.post(
    "/leads/{lead_id}/activities",
    response_model=LeadRead,
    status_code=status.HTTP_201_CREATED,
)
def add_activity(
    lead_id: int,
    body: ActivityCreate = Body(...),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadRead:
    return leads_service.add_activity_read(db, lead_id, body, actor)


@router.post("/leads/{lead_id}/enquiry-code", response_model=LeadCreateResult)
def link_enquiry_code(
    lead_id: int,
    body: LinkCodeIn = Body(...),
    db: Session = Depends(get_db),
    actor: CurrentUser = Depends(_any_user),
) -> LeadCreateResult:
    return leads_service.link_enquiry_code_read(db, lead_id, body.code, actor)
