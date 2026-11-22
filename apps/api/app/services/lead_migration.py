"""One-off data copy: legacy ``contact_leads`` rows -> ``leads`` (lead-crm R3.9-R3.11).

Called from Alembic revision 0024. It deliberately uses plain SQL on the given
connection (not ORM models) so the migration keeps working even if the models
change later. ``contact_leads`` itself is never modified; it stays read-only for
rollback.

Rules:
- the phone is normalised to a 10-digit Indian mobile; rows whose phone cannot be
  normalised are skipped (they would violate the phone CHECK) and counted;
- every copied lead goes to the first active branch (``contact_leads`` has no
  branch), with "Branch unknown (migrated)" in its first note;
- a repeat phone attaches to the lead already created for it (as an extra note)
  instead of creating a second lead, mirroring the duplicate rule (R6.1);
- created_at / last_activity_at keep the original ``contact_leads.created_at``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.phone import normalize_indian_mobile

_NOTE_MAX = 2000
_NAME_MAX = 120


@dataclass(frozen=True)
class CopyResult:
    copied: int
    attached: int
    skipped: int


def _note_text(message: str | None, email: str | None) -> str:
    parts = [(message or "").strip()]
    if email and email.strip():
        parts.append(f"Email: {email.strip()}")
    parts.append("Branch unknown (migrated)")
    body = "\n".join(p for p in parts if p)
    return body[:_NOTE_MAX]


def copy_contact_leads(conn: Connection) -> CopyResult:
    """Copy every ``contact_leads`` row into ``leads`` + a first ``note`` activity."""
    location_id = conn.execute(
        text("SELECT id FROM locations WHERE is_active ORDER BY id LIMIT 1")
    ).scalar()
    if location_id is None:
        return CopyResult(copied=0, attached=0, skipped=0)

    rows = conn.execute(
        text(
            "SELECT id, name, phone, email, message, created_at "
            "FROM contact_leads ORDER BY created_at, id"
        )
    ).mappings()

    lead_by_phone: dict[str, int] = {}
    copied = attached = skipped = 0
    for row in rows:
        phone = normalize_indian_mobile(row["phone"] or "")
        if phone is None:
            skipped += 1
            continue
        note = _note_text(row["message"], row["email"])
        lead_id = lead_by_phone.get(phone)
        if lead_id is None:
            name = (row["name"] or "").strip()[:_NAME_MAX] or None
            lead_id = conn.execute(
                text(
                    "INSERT INTO leads (location_id, phone, name, source, status, "
                    "channel, last_activity_at, created_at, updated_at) "
                    "VALUES (:location_id, :phone, :name, 'contact_form', 'new', "
                    "'direct', :ts, :ts, :ts) RETURNING id"
                ),
                {
                    "location_id": location_id,
                    "phone": phone,
                    "name": name,
                    "ts": row["created_at"],
                },
            ).scalar_one()
            lead_by_phone[phone] = lead_id
            copied += 1
        else:
            attached += 1
            conn.execute(
                text(
                    "UPDATE leads SET last_activity_at = GREATEST(last_activity_at, :ts) "
                    "WHERE id = :id"
                ),
                {"id": lead_id, "ts": row["created_at"]},
            )
        conn.execute(
            text(
                "INSERT INTO lead_activities (lead_id, type, text, created_at) "
                "VALUES (:lead_id, 'note', :text, :ts)"
            ),
            {"lead_id": lead_id, "text": note, "ts": row["created_at"]},
        )
    return CopyResult(copied=copied, attached=attached, skipped=skipped)
