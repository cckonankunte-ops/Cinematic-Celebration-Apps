"""SQLAlchemy ORM models.

Importing every model here ensures Base.metadata is fully populated for Alembic
autogenerate and for the test harness.
"""

from app.models.booking import Booking
from app.models.booking_event import BookingEvent
from app.models.booking_item import BookingItem
from app.models.cake import Cake
from app.models.combo_item import ComboItem
from app.models.contact_lead import ContactLead
from app.models.location import Location
from app.models.occasion import Occasion
from app.models.payment import Payment
from app.models.plan import Plan, PlanGalleryImage
from app.models.slot import Slot
from app.models.special_decor_item import SpecialDecorItem
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "Booking",
    "BookingEvent",
    "BookingItem",
    "Cake",
    "ComboItem",
    "ContactLead",
    "Location",
    "Occasion",
    "Payment",
    "Plan",
    "PlanGalleryImage",
    "Slot",
    "SpecialDecorItem",
    "User",
    "UserRole",
]
