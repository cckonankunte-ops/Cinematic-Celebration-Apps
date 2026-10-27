"""One-off bootstrap: ensure roles exist and create/activate an admin user.

Useful on a fresh database (local dev / a new environment) where no users
exist yet, so ``set_password`` has nothing to update. Idempotent: running it
again updates the existing user's password and keeps a single ``admin``/
``staff`` role pair.

Reuses the app's own argon2 hashing so the hash is login-compatible.

Run from apps/api with the venv active and DATABASE_URL configured in .env:

    # create (or update) an admin user
    python -m scripts.bootstrap_admin <username> <password>

    # create a staff user at a location
    python -m scripts.bootstrap_admin <username> <password> --role staff --location-id 1
"""

from __future__ import annotations

import argparse

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.user_role import UserRole


def _ensure_role(db, name: str) -> int:
    """Return the id of role ``name``, creating it if absent."""
    role = db.execute(
        select(UserRole).where(UserRole.name == name)
    ).scalar_one_or_none()
    if role is None:
        role = UserRole(name=name)
        db.add(role)
        db.flush()
    return role.id


def bootstrap(
    username: str, password: str, *, role: str, location_id: int | None
) -> None:
    """Create or update ``username`` with the given role, active + ready."""
    with SessionLocal() as db:
        role_id = _ensure_role(db, role)
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if user is None:
            user = User(username=username)
            db.add(user)
        user.password_hash = hash_password(password)
        user.role_id = role_id
        user.location_id = location_id
        user.is_active = True
        user.must_reset_password = False
        db.commit()
    print(
        f"User {username!r} ready (role={role}, "
        f"location_id={location_id if location_id is not None else '-'}). "
        "You can log in now."
    )


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Bootstrap an admin/staff user.")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("--role", choices=("admin", "staff"), default="admin")
    parser.add_argument("--location-id", type=int, default=None)
    args = parser.parse_args()
    bootstrap(
        args.username,
        args.password,
        role=args.role,
        location_id=args.location_id,
    )


if __name__ == "__main__":
    main()
