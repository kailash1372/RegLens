"""Deterministic evaluation of verified regulatory rules."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.product import CanonicalProductSnapshot
from app.models.regulatory import RegulatoryFinding, RegulatoryRule, VerificationStatus


def rule_can_evaluate(
    rule: RegulatoryRule,
    *,
    evaluated_at: datetime | None = None,
) -> bool:
    """Return whether a rule has enough verified structure for automation."""
    moment = _as_utc(evaluated_at or datetime.now(UTC))
    return (
        rule.verification_status is VerificationStatus.VERIFIED
        and rule.threshold is not None
        and bool(rule.unit)
        and rule.comparator in {"<", "<=", ">", ">=", "="}
        and (rule.effective_from is None or _as_utc(rule.effective_from) <= moment)
        and (rule.effective_until is None or moment <= _as_utc(rule.effective_until))
    )


def evaluate_snapshot(
    product_id: str,
    snapshot: CanonicalProductSnapshot,
    rule: RegulatoryRule,
    *,
    evaluated_at: datetime | None = None,
) -> RegulatoryFinding | None:
    """Evaluate caffeine against a verified maximum, preserving applicability notes."""
    moment = _as_utc(evaluated_at or datetime.now(UTC))
    if (
        not rule_can_evaluate(rule, evaluated_at=moment)
        or rule.subject != "caffeine"
        or rule.threshold is None
        or (rule.rule_type == "maximum-per-serving" and not snapshot.caffeine_basis_available)
    ):
        return None
    observed = snapshot.caffeine_mg
    if observed is None:
        return None
    threshold = rule.threshold
    comparator = rule.comparator
    exceeds = {
        "<": observed >= threshold,
        "<=": observed > threshold,
        ">": observed <= threshold,
        ">=": observed < threshold,
        "=": observed != threshold,
    }[comparator]
    finding_type = "exceeds_threshold" if exceeds else "within_threshold"
    status = "attention" if exceeds else "context"
    difference = observed - threshold
    explanation = (
        f"The scraped formulation contains {observed:g} {rule.unit} caffeine per serving. "
        f"The verified {rule.jurisdiction} rule uses a {threshold:g} {rule.unit} {comparator} "
        "for the applicable category. Market-specific formulations may differ."
    )
    return RegulatoryFinding(
        product_id=product_id,
        rule_id=rule.id,
        finding_type=finding_type,
        observed_value=observed,
        threshold_value=threshold,
        difference=difference,
        unit=rule.unit or "",
        status=status,
        explanation_template=explanation,
        evaluated_at=moment,
    )


def _as_utc(value: datetime) -> datetime:
    """Make legacy naive timestamps deterministic before effective-date comparison."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
