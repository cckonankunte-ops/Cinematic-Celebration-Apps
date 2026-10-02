"""FastAPI application factory and router registration.

Task 1 wires the app skeleton: logging, CORS (explicit allowlist), and the
health endpoint. Auth, public, and admin routers are registered in later tasks.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger

log = get_logger("app.main")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Cinematic Celebration API",
        version="0.1.0",
        description="Booking platform API (Phase 1 — manual payments, no gateway).",
    )

    # Explicit CORS allowlist from env; credentials enabled; never "*".
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["health"])
    def healthz() -> dict[str, str]:
        """Liveness/readiness probe for uptime monitoring."""
        return {"status": "ok"}

    # Router registration (added in later tasks):
    # app.include_router(auth.router)
    # app.include_router(public_* routers)
    # app.include_router(admin_* routers)

    log.info("app_created", environment=settings.ENVIRONMENT)
    return app


app = create_app()
