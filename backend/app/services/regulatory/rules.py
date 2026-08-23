"""Deterministic evaluation of verified regulatory rules."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.product import CanonicalProductSnapshot
from app.models.regulatory import RegulatoryFinding, RegulatoryRule, VerificationStatus


def rule_can_evaluate(rule: RegulatoryRule) -> bool:
    """Return whether a rule has enough verified structure for automation."""
    return (
        rule.verification_status is VerificationStatus.VERIFIED
        and rule.threshold is not None
        and bool(rule.unit)
        and rule.comparator in {"<", "<=", ">", ">=", "="}
    )


def evaluate_snapshot(
    product_id: str,
    snapshot: CanonicalProductSnapshot,
    rule: RegulatoryRule,
    *,
    evaluated_at: datetime | None = None,
) -> RegulatoryFinding | None:
    """Evaluate caffeine against a verified maximum, preserving applicability notes."""
    if not rule_can_evaluate(rule) or rule.subject != "caffeine" or rule.threshold is None:
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
        evaluated_at=evaluated_at or datetime.now(UTC),
    )
