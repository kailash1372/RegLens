"""Source-grounded regulatory and recall domain contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class VerificationStatus(StrEnum):
    """Evidence quality used to gate automated rule evaluation."""

    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RegulatorySourceStatus(StrEnum):
    """Current retrieval state without changing the evidence's verification level."""

    CURRENT = "current"
    REFRESH_FAILED = "refresh_failed"


class RegulatorySource(BaseModel):
    """An authoritative document or data source with retained provenance."""

    id: str
    authority: str
    jurisdiction: str
    title: str
    source_url: HttpUrl
    retrieved_at: datetime
    source_type: str
    content: str
    evidence_text: str
    evidence_anchor: str | None = None
    content_hash: str | None = None
    status: RegulatorySourceStatus = RegulatorySourceStatus.CURRENT
    last_error: str | None = None


class RegulatoryRule(BaseModel):
    """A source-backed rule; only VERIFIED rules may create findings."""

    id: str
    source_id: str
    jurisdiction: str
    authority: str
    category: str
    subject: str
    rule_type: str
    comparator: str
    threshold: float | None = None
    unit: str | None = None
    affected_population: str | None = None
    applicability_notes: str
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    verification_status: VerificationStatus
    evidence_excerpt: str


class RegulatoryFinding(BaseModel):
    """Deterministic comparison between a snapshot fact and a verified rule."""

    product_id: str
    rule_id: str
    finding_type: str
    observed_value: float
    threshold_value: float
    difference: float
    unit: str
    status: str
    explanation_template: str
    evaluated_at: datetime


class RecallMatchType(StrEnum):
    """Conservative entity resolution levels for enforcement records."""

    EXACT_PRODUCT = "exact_product"
    PRODUCT_FAMILY = "product_family"
    BRAND = "brand"
    NO_MATCH = "no_match"


class RecallRecord(BaseModel):
    """Normalized official recall/enforcement record."""

    id: str
    authority: str
    jurisdiction: str
    product_description: str
    brand_manufacturer: str | None = None
    reason: str
    classification_status: str | None = None
    event_date: datetime | None = None
    source_url: HttpUrl
    retrieved_at: datetime
    match_type: RecallMatchType = RecallMatchType.NO_MATCH
    matched_product_id: str | None = None


class RegulatoryDiscovery(BaseModel):
    """Curated, source-backed entry point into the regulatory evidence graph."""

    id: str
    topic: str
    title: str
    summary: str
    authority: str
    jurisdiction: str
    evidence_status: VerificationStatus
    source_title: str
    source_url: HttpUrl
    source_retrieved_at: datetime
    ask_prompt: str
    related_product_ids: list[str] = Field(default_factory=list)
