"""Public contact form endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limiter
from app.schemas.booking import ContactCreate, ContactResult
from app.services import booking as booking_service

router = APIRouter(prefix="/api/v1/public", tags=["public-contact"])

_SUCCESS_MESSAGE = "Thanks you for contacting us! We will get back to you soon"


@router.post(
    "/contact", response_model=ContactResult, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def submit_contact(
    request: Request,
    body: ContactCreate,
    db: Session = Depends(get_db),
) -> ContactResult:
    """Save a contact lead and return a success message."""
    booking_service.create_contact_lead(db, body)
    return ContactResult(message=_SUCCESS_MESSAGE)
