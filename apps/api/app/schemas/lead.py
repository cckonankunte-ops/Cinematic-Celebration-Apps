"""Lead CRM request/response schemas (lead-crm).

Public inputs ignore unknown fields, so a client cannot set status, assignment,
notes or reasons (R2.13). Malformed attribution is dropped instead of failing the
request (R17.8). Phones are normalised to 10 digits; an unusable phone is a 422.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from app.core.phone import normalize_indian_mobile
from app.models.lead import (
    CLOSE_REASON_TEXT_MAX,
    ENQUIRY_CODE_PATTERN,
    NAME_MAX,
    TEXT_MAX,
    URLISH_MAX,
    UTM_MAX,
)

ManualSource = Literal["whatsapp", "whatsapp_ad", "phone", "walk_in", "instagram_dm", "other"]
EnquirySource = Literal["homepage_form", "contact_form"]
ManualStatus = Literal["new", "contacted", "follow_up", "not_interested", "lost"]
CloseReason = Literal[
    "price_budget",
    "date_not_available",
    "booked_elsewhere",
    "no_response",
    "just_enquiring",
    "other",
]
ManualActivityType = Literal["note", "call", "whatsapp"]


def _phone(value: str) -> str:
    normalised = normalize_indian_mobile(value or "")
    if normalised is None:
        raise ValueError("phone must be a valid Indian mobile number")
    return normalised


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value.strip() if isinstance(value, str) else value


class AttributionIn(BaseModel):
    """Landing attribution captured by the browser (all optional)."""

    model_config = ConfigDict(extra="ignore")

    utm_source: str | None = Field(default=None, max_length=UTM_MAX)
    utm_medium: str | None = Field(default=None, max_length=UTM_MAX)
    utm_campaign: str | None = Field(default=None, max_length=UTM_MAX)
    utm_content: str | None = Field(default=None, max_length=UTM_MAX)
    utm_term: str | None = Field(default=None, max_length=UTM_MAX)
    fbclid: str | None = Field(default=None, max_length=URLISH_MAX)
    gclid: str | None = Field(default=None, max_length=URLISH_MAX)
    landing_path: str | None = Field(default=None, max_length=URLISH_MAX)
    referrer: str | None = Field(default=None, max_length=URLISH_MAX)
    landed_at: datetime | None = None


class _WithAttribution(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attribution: AttributionIn | None = None

    @field_validator("attribution", mode="wrap")
    @classmethod
    def _drop_malformed(cls, value: Any, handler: Any) -> AttributionIn | None:
        try:
            return handler(value)
        except ValidationError:
            return None


class WebsiteLeadIn(_WithAttribution):
    """Step 1 of the booking wizard (R2)."""

    lead_token: str | None = Field(default=None, max_length=64)
    location_id: int
    phone: str
    name: str | None = Field(default=None, max_length=NAME_MAX)
    preferred_date: date | None = None
    plan_id: int | None = None
    start_time: time | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    guests: int | None = Field(default=None, ge=1, le=200)

    _check_phone = field_validator("phone")(_phone)
    _check_name = field_validator("name", mode="before")(_blank_to_none)


class EnquiryIn(_WithAttribution):
    """Homepage quick enquiry and contact page form (R3)."""

    source: EnquirySource
    location_id: int
    phone: str
    name: str = Field(min_length=1, max_length=NAME_MAX)
    preferred_date: date | None = None
    message: str | None = Field(default=None, max_length=TEXT_MAX)
    email: str | None = Field(default=None, max_length=254)
    # Honeypot: real visitors never fill it (hidden field). R3.7
    website: str | None = None

    _check_phone = field_validator("phone")(_phone)
    _check_blank = field_validator("message", "email", mode="before")(_blank_to_none)


class EnquiryCodeIn(_WithAttribution):
    """WhatsApp enquiry code registration (R18.3)."""

    code: str = Field(pattern=ENQUIRY_CODE_PATTERN)
    location_id: int | None = None

    @field_validator("code", mode="before")
    @classmethod
    def _upper(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value


class LeadTokenOut(BaseModel):
    lead_token: str


class OkOut(BaseModel):
    message: str


# --- admin inputs -----------------------------------------------------------


class LeadCreate(BaseModel):
    """Receptionist quick-add (R4)."""

    model_config = ConfigDict(extra="forbid")

    location_id: int
    phone: str
    source: ManualSource = "whatsapp"
    name: str | None = Field(default=None, max_length=NAME_MAX)
    note: str | None = Field(default=None, max_length=TEXT_MAX)
    follow_up_at: datetime | None = None
    enquiry_code: str | None = Field(default=None, max_length=12)

    _check_phone = field_validator("phone")(_phone)
    _check_blank = field_validator("name", "note", "enquiry_code", mode="before")(
        _blank_to_none
    )


class LeadUpdate(BaseModel):
    """Partial update from the lead detail page (R7.5). Omitted fields are unchanged;
    ``assigned_user_id`` / ``follow_up_at`` may be sent as null to clear them."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=NAME_MAX)
    status: str | None = None  # validated in the service (manual vs booking-driven)
    close_reason: CloseReason | None = None
    close_reason_text: str | None = Field(default=None, max_length=CLOSE_REASON_TEXT_MAX)
    assigned_user_id: int | None = None
    follow_up_at: datetime | None = None


class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ManualActivityType
    text: str | None = Field(default=None, max_length=TEXT_MAX)

    _check_blank = field_validator("text", mode="before")(_blank_to_none)


class LinkCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=12)


# --- reads ------------------------------------------------------------------


class ActivityRead(BaseModel):
    id: int
    type: str
    text: str | None
    data: dict | None
    author_user_id: int | None
    author_name: str | None
    created_at: datetime


class LeadBrief(BaseModel):
    id: int
    location_id: int
    location_name: str
    status: str
    source: str
    created_at: datetime


class AttributionSummary(BaseModel):
    utm_source: str | None
    utm_medium: str | None
    utm_campaign: str | None
    landing_path: str | None
    referrer_domain: str | None
    has_fbclid: bool
    has_gclid: bool


class LeadRead(BaseModel):
    id: int
    location_id: int
    phone: str
    name: str | None
    source: str
    status: str
    channel: str
    close_reason: str | None
    close_reason_text: str | None
    assigned_user_id: int | None
    assigned_user_name: str | None
    follow_up_at: datetime | None
    last_activity_at: datetime
    first_contacted_at: datetime | None
    is_uncontacted: bool
    minutes_since_created: int
    booking_id: int | None
    booking_reference: str | None
    preferred_date: date | None
    plan_id: int | None
    plan_title: str | None
    start_time: time | None
    duration_minutes: int | None
    guests: int | None
    message: str | None
    attribution: AttributionSummary
    enquiry_code: str | None
    created_at: datetime
    activities: list[ActivityRead] = Field(default_factory=list)
    same_phone_leads: list[LeadBrief] = Field(default_factory=list)


class LeadCreateResult(BaseModel):
    lead: LeadRead
    created: bool
    warning: str | None = None
    code_used_by_lead_id: int | None = None
