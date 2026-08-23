"""Typed contracts for the two-stage evidence-grounded question flow."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.product import ServingSize


class QueryIntent(BaseModel):
    """Small, validated query-understanding result."""

    intent: str = "product_regulatory_question"
    products: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    jurisdictions: list[str] = Field(default_factory=list)


class ChatHistoryMessage(BaseModel):
    """One bounded prior message supplied for follow-up context."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4_000)


class AskProductFact(BaseModel):
    """Manufacturer-sourced facts rendered separately from interpretation."""

    product_id: str
    display_name: str
    manufacturer: str
    market: str
    source_url: str
    scraped_at: datetime
    caffeine_mg: float | None = None
    sugar_g: float | None = None
    calories: float | None = None
    serving_size: ServingSize


class AskResult(BaseModel):
    """Answer plus structured evidence for a UI to render transparently."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    product_facts: list[AskProductFact] = Field(default_factory=list)
    intent: QueryIntent = Field(default_factory=QueryIntent)
    evidence: list[dict[str, str]] = Field(default_factory=list)
    findings: list[dict[str, object]] = Field(default_factory=list)
    recalls: list[dict[str, object]] = Field(default_factory=list)
    answer_mode: Literal["openrouter", "deterministic"] = "deterministic"
    model: str | None = None
