"""Admin advance-rule service (admin-only, per-location).

CRUD over per-location advance rules. The (location_id, min_total_paise) unique
index backs a friendly duplicate-threshold error (409). Value validation
(non-negative) is enforced by the Pydantic schema before we reach here.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, SlotUnavailableError
from app.models.advance_rule import AdvanceRule
from app.schemas.advance_rule import AdvanceRuleCreate, AdvanceRuleRead


class DuplicateThresholdError(SlotUnavailableError):
    """A rule with this threshold already exists for the location (409)."""

    code = "ADVANCE_RULE_DUPLICATE_THRESHOLD"


def list_advance_rules(db: Session, location_id: int) -> list[AdvanceRule]:
    return list(
        db.execute(
            select(AdvanceRule)
            .where(AdvanceRule.location_id == location_id)
            .order_by(AdvanceRule.min_total_paise)
        ).scalars()
    )


def create_advance_rule(
    db: Session, location_id: int, data: AdvanceRuleCreate
) -> AdvanceRule:
    rule = AdvanceRule(
        location_id=location_id,
        min_total_paise=data.min_total_paise,
        advance_paise=data.advance_paise,
        is_active=data.is_active,
    )
    db.add(rule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateThresholdError(
            "An advance rule for this amount already exists at this branch."
        ) from exc
    db.refresh(rule)
    return rule


def delete_advance_rule(db: Session, location_id: int, rule_id: int) -> None:
    rule = db.get(AdvanceRule, rule_id)
    if rule is None or rule.location_id != location_id:
        raise NotFoundError("Advance rule not found.")
    db.delete(rule)
    db.commit()


def to_advance_rule_read(rule: AdvanceRule) -> AdvanceRuleRead:
    return AdvanceRuleRead(
        id=rule.id,
        location_id=rule.location_id,
        min_total_paise=rule.min_total_paise,
        advance_paise=rule.advance_paise,
        is_active=rule.is_active,
    )
