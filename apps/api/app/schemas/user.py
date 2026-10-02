"""Auth / user request & response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=250)
    password: str = Field(min_length=1, max_length=1024)


class CurrentUserRead(BaseModel):
    id: int
    username: str
    role: str
    location_id: int | None
