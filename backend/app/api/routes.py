"""Core product and health endpoints used by the React client."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.models.ask import AskResult, ChatHistoryMessage
from app.models.health import ScraperHealth
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductRecord, ProductSummary
from app.models.regulatory import (
    RecallRecord,
    RegulatoryDiscovery,
    RegulatoryFinding,
    RegulatoryRule,
    RegulatorySource,
)
from app.models.scraper import ProductScraperAssets
from app.services.products.service import ProductService
from app.services.regulatory.service import RegulatoryService

router = APIRouter(prefix="/api")


def get_product_service(request: Request) -> ProductService:
    """Resolve the application-owned product service."""
    return request.app.state.product_service


def get_regulatory_service(request: Request) -> RegulatoryService:
    """Resolve the source-grounded regulatory service."""
    return request.app.state.regulatory_service


@router.get("/products", response_model=list[ProductSummary])
def list_products(request: Request) -> list[ProductSummary]:
    """List the supported product catalog."""
    return get_product_service(request).repository.list_products()


@router.get("/products/compare", response_model=list[ProductRecord])
def compare_products(request: Request, ids: str = "") -> list[ProductRecord]:
    """Return selected products using backend-held current snapshots."""
    selected_ids = [product_id.strip() for product_id in ids.split(",") if product_id.strip()]
    if not selected_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ids is required"
        )
    products = [
        get_product_service(request).repository.get_product(product_id)
        for product_id in selected_ids
    ]
    missing = [
        product_id
        for product_id, product in zip(selected_ids, products, strict=True)
        if product is None
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown product: {missing[0]}"
        )
    return [product for product in products if product is not None]


@router.get("/products/{product_id}", response_model=ProductRecord)
def get_product(request: Request, product_id: str) -> ProductRecord:
    """Get a Product Passport's current canonical facts."""
    product = get_product_service(request).repository.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.get("/products/{product_id}/assets", response_model=ProductScraperAssets)
def get_product_scraper_assets(request: Request, product_id: str) -> ProductScraperAssets:
    """Return latest accepted collector transport metadata for one product."""
    assets = get_product_service(request).repository.get_scraper_assets(product_id)
    if assets is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return assets


@router.get(
    "/products/{product_id}/ingredients",
    response_model=list[NormalizedIngredient],
)
def get_normalized_product_ingredients(
    request: Request,
    product_id: str,
) -> list[NormalizedIngredient]:
    """Return preserved label names with only reviewed canonical matches."""
    service = get_product_service(request)
    if service.repository.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return service.repository.list_ingredients(product_id)


@router.post("/products/{product_id}/refresh", response_model=ProductRecord)
def refresh_product(request: Request, product_id: str) -> ProductRecord:
    """Refresh a product while preserving its last valid snapshot on failures."""
    service = get_product_service(request)
    if service.repository.get_product(product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product = service.refresh(product_id)
    get_regulatory_service(request).evaluate_product(product)
    return product


@router.get("/scrapers/health", response_model=list[ScraperHealth])
def list_scraper_health(request: Request) -> list[ScraperHealth]:
    """Expose schema validity and source health without pretending to self-heal."""
    return get_product_service(request).repository.list_health()


@router.get("/sources", response_model=list[RegulatorySource])
def list_regulatory_sources(request: Request) -> list[RegulatorySource]:
    """List regulator provenance and retained evidence excerpts."""
    return get_regulatory_service(request).repository.list_sources()


@router.post("/sources/refresh", response_model=list[RegulatorySource])
def refresh_regulatory_sources(request: Request) -> list[RegulatorySource]:
    """Refresh the configured primary corpus while preserving last-known-good text."""
    return get_regulatory_service(request).refresh_sources()


@router.get("/rules", response_model=list[RegulatoryRule])
def list_regulatory_rules(request: Request) -> list[RegulatoryRule]:
    """List rules with verification status and applicability notes."""
    return get_regulatory_service(request).repository.list_rules()


@router.get("/discoveries", response_model=list[RegulatoryDiscovery])
def list_regulatory_discoveries(request: Request) -> list[RegulatoryDiscovery]:
    """Return curated impact cards generated from current verified evidence."""
    return get_regulatory_service(request).list_discoveries()


@router.get("/findings", response_model=list[RegulatoryFinding])
def list_regulatory_findings(
    request: Request, product_id: str | None = None
) -> list[RegulatoryFinding]:
    """List deterministic findings generated from verified rules."""
    return get_regulatory_service(request).repository.list_findings(product_id)


@router.get("/recalls", response_model=list[RecallRecord])
def list_recalls(request: Request, product_id: str | None = None) -> list[RecallRecord]:
    """List official recall records matched conservatively to catalog products."""
    return get_regulatory_service(request).repository.list_recalls(product_id)


class AskRequest(BaseModel):
    """Natural-language investigation question."""

    question: str = Field(min_length=3, max_length=2_000)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)
    context_products: list[str] = Field(default_factory=list, max_length=10)


@router.post("/ask", response_model=AskResult)
def ask_reglens(request: Request, payload: AskRequest) -> AskResult:
    """Answer from stored facts and evidence, using OpenRouter only when configured."""
    return request.app.state.ask_service.ask(
        payload.question,
        history=payload.history,
        context_product_ids=payload.context_products,
    )
