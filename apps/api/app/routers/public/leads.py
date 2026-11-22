"""Public lead capture endpoints (lead-crm R2, R3, R18).

Deliberately public (no auth), rate-limited per client IP. Responses carry no
lead data: only the Step 1 token or a fixed message (R15.3). Thin router: all
rules live in ``services/leads.py``.
"""

from fastapi import APIRouter, Body, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.ratelimit import limiter
from app.schemas.lead import EnquiryCodeIn, EnquiryIn, LeadTokenOut, OkOut, WebsiteLeadIn
from app.services import leads as leads_service

router = APIRouter(prefix="/api/v1/public", tags=["public-leads"])

ENQUIRY_THANKS = "Thanks! Our team will call or WhatsApp you shortly."


@router.post("/leads", response_model=LeadTokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def capture_lead(
    request: Request,
    body: WebsiteLeadIn = Body(...),
    db: Session = Depends(get_db),
) -> LeadTokenOut:
    """Booking wizard Step 1: create or update the lead, return its token."""
    return LeadTokenOut(lead_token=leads_service.capture_website_lead(db, body))


@router.post("/enquiries", response_model=OkOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_enquiry(
    request: Request,
    body: EnquiryIn = Body(...),
    db: Session = Depends(get_db),
) -> OkOut:
    """Homepage / contact page enquiry. A filled honeypot gets the same reply."""
    leads_service.create_enquiry_lead(db, body)
    return OkOut(message=ENQUIRY_THANKS)


@router.post(
    "/enquiry-codes",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
@limiter.limit("10/minute")
def register_enquiry_code(
    request: Request,
    body: EnquiryCodeIn = Body(...),
    db: Session = Depends(get_db),
) -> Response:
    """Remember a WhatsApp enquiry code and its attribution (no personal data)."""
    leads_service.register_enquiry_code(db, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
