"""FastAPI application factory and router registration.

Task 1 wires the app skeleton: logging, CORS (explicit allowlist), and the
health endpoint. Auth, public, and admin routers are registered in later tasks.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import limiter
from app.routers import auth
from app.routers.admin import analytics as admin_analytics
from app.routers.admin import bookings as admin_bookings
from app.routers.admin import catalog as admin_catalog
from app.routers.admin import payments as admin_payments
from app.routers.admin import sheets as admin_sheets
from app.routers.admin import users as admin_users
from app.routers.public import bookings as public_bookings
from app.routers.public import contact as public_contact
from app.routers.public import locations as public_locations
from app.routers.public import plans as public_plans

log = get_logger("app.main")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Cinematic Celebration API",
        version="0.1.0",
        description="Booking platform API (Phase 1 — manual payments, no gateway).",
    )

    # Rate limiting (slowapi), keyed on the real client IP.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Explicit CORS allowlist from env; credentials enabled; never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        """Liveness/readiness probe for uptime monitoring."""
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(public_locations.router)
    app.include_router(public_plans.router)
    app.include_router(public_bookings.router)
    app.include_router(public_contact.router)
    app.include_router(admin_catalog.router)
    app.include_router(admin_users.router)
    app.include_router(admin_bookings.router)
    app.include_router(admin_payments.router)
    app.include_router(admin_sheets.router)
    app.include_router(admin_analytics.router)
    # Remaining admin routers are registered in later tasks.

    log.info("app_created", environment=settings.ENVIRONMENT)
    return app


app = create_app()
