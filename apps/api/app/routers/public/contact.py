"""Public contact form endpoint (legacy path, kept for compatibility).

Submissions are stored as ``contact_form`` leads (lead-crm R3.8); the old
``contact_leads`` table is no longer written. New forms post to
``/public/enquiries`` instead.
"""

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limiter
from app.schemas.booking import ContactCreate, ContactResult
from app.services import leads as leads_service

router = APIRouter(prefix="/api/v1/public", tags=["public-contact"])

_SUCCESS_MESSAGE = "Thanks you for contacting us! We will get back to you soon"


@router.post(
    "/contact", response_model=ContactResult, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def submit_contact(
    request: Request,
    body: ContactCreate = Body(...),
    db: Session = Depends(get_db),
) -> ContactResult:
    """Save a contact-form lead and return a success message."""
    leads_service.create_contact_form_lead(db, body)
    return ContactResult(message=_SUCCESS_MESSAGE)
