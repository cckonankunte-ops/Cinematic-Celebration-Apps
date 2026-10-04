"""One-off admin helper: list users or set a user's password.

Reuses the app's own argon2 hashing (app.core.security.hash_password) so the
resulting hash is always compatible with login verification, and marks the
account active so it can be used immediately.

Run from apps/api with the venv active and DATABASE_URL configured in .env:

    # list all users (id, username, role, location, active)
    python -m scripts.set_password --list

    # set a password for a username
    python -m scripts.set_password <username> <new_password>
"""

from __future__ import annotations

import sys

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User


def list_users() -> None:
    """Print every user with id, username, role, location, and active flag."""
    with SessionLocal() as db:
        rows = db.execute(
            text(
                "SELECT u.id, u.username, r.name AS role, u.location_id, "
                "u.is_active "
                "FROM users u JOIN user_roles r ON u.role_id = r.id "
                "ORDER BY u.id"
            )
        ).all()
    print(f"{'id':>3}  {'username':<24} {'role':<8} {'loc':<4} active")
    for r in rows:
        print(
            f"{r.id:>3}  {r.username:<24} {r.role:<8} "
            f"{str(r.location_id or '-'):<4} {r.is_active}"
        )


def set_password(username: str, new_password: str) -> None:
    """Set a known password for ``username`` and clear the reset flag."""
    with SessionLocal() as db:
        user = db.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()
        if user is None:
            print(f"No user named {username!r}. Use --list to see usernames.")
            raise SystemExit(1)
        user.password_hash = hash_password(new_password)
        user.must_reset_password = False
        user.is_active = True
        db.commit()
    print(f"Password updated for {username!r}. You can log in now.")


def main() -> None:
    """CLI entry point."""
    args = sys.argv[1:]
    if args == ["--list"]:
        list_users()
        return
    if len(args) == 2:
        set_password(args[0], args[1])
        return
    print(__doc__)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
