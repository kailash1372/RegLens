"""FastAPI application factory for RegLens."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import Settings, get_settings
from app.core.rate_limit import InMemoryRateLimiter
from app.data.catalog import CATALOG
from app.db.database import Database
from app.models.product import CanonicalProductSnapshot
from app.repositories.products import ProductRepository
from app.repositories.regulatory import RegulatoryRepository
from app.services.llm.ask import AskService
from app.services.llm.client import OpenRouterClient
from app.services.products.providers import BrightDataProductProvider, FixtureProductProvider
from app.services.products.service import ProductService
from app.services.regulatory.service import RegulatoryService
from app.services.retrieval.fts import RegulatoryRetriever


def build_product_service(settings: Settings) -> ProductService:
    """Build the configured provider boundary and SQLite repository."""
    database = Database(settings.database_path)
    repository = ProductRepository(database)
    fixture_directory = Path(__file__).parent / "data" / "fixtures"
    fixture_provider = FixtureProductProvider(
        fixture_directory,
        collector_ids=settings.brightdata_collectors,
    )
    provider = (
        fixture_provider
        if settings.data_provider == "fixture"
        else BrightDataProductProvider(
            api_token=settings.brightdata_api_token,
            base_url=settings.brightdata_api_base_url,
            collector_ids=settings.brightdata_collectors,
            product_urls=_fixture_source_urls(fixture_provider),
            product_catalog={product.id: product for product in CATALOG},
            trigger_path=settings.brightdata_trigger_path,
            poll_path=settings.brightdata_poll_path,
            output_path=settings.brightdata_output_path,
            poll_interval_seconds=settings.brightdata_poll_interval_seconds,
            max_poll_attempts=settings.brightdata_max_poll_attempts,
        )
    )
    return ProductService(repository, provider, catalog=CATALOG)


def _fixture_source_urls(provider: FixtureProductProvider) -> dict[str, str]:
    """Use each supported product's official fixture URL as live collector input."""
    urls: dict[str, str] = {}
    for product in CATALOG:
        collected_result = provider.fetch(product.id)
        snapshot: CanonicalProductSnapshot = collected_result.snapshot
        urls[product.id] = str(snapshot.source.url)
    return urls


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a testable application instance with initialized catalog data."""
    configured_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        service = build_product_service(configured_settings)
        service.repository.database.initialize()
        # Refresh deterministic fixtures so older local databases receive newly
        # validated evidence assets. Live mode must not trigger remote collectors
        # merely because the API restarted.
        service.seed_catalog(
            CATALOG,
            refresh_existing=configured_settings.data_provider == "fixture",
        )
        app.state.product_service = service
        app.state.settings = configured_settings
        app.state.rate_limiter = InMemoryRateLimiter()
        regulatory_service = RegulatoryService(
            RegulatoryRepository(service.repository.database), service.repository
        )
        regulatory_service.seed()
        regulatory_service.evaluate_catalog()
        app.state.regulatory_service = regulatory_service
        app.state.ask_service = AskService(
            service.repository,
            regulatory_service.repository,
            RegulatoryRetriever(service.repository.database),
            OpenRouterClient(
                configured_settings.openrouter_api_key, configured_settings.openrouter_model
            ),
        )
        yield

    app = FastAPI(title="RegLens API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return a minimal liveness signal."""
        return {"status": "ok"}

    return app


app = create_app()
