"""Application service for evidence seeding and deterministic findings."""

from __future__ import annotations

from app.models.product import ProductRecord
from app.models.regulatory import RegulatoryDiscovery, RegulatoryFinding, RegulatorySource
from app.repositories.products import ProductRepository
from app.repositories.regulatory import RegulatoryRepository
from app.services.regulatory.discoveries import build_regulatory_discoveries
from app.services.regulatory.ingestion import RegulatorySourceIngestor
from app.services.regulatory.recalls import attach_match
from app.services.regulatory.rules import evaluate_snapshot
from app.services.regulatory.seed import red_bull_openfda_recall, seed_regulatory_evidence


class RegulatoryService:
    """Coordinate stored primary evidence with product snapshots."""

    def __init__(self, repository: RegulatoryRepository, products: ProductRepository) -> None:
        self.repository = repository
        self.products = products

    def seed(self) -> None:
        """Ensure the small offline evidence set exists."""
        seed_regulatory_evidence(self.repository.database)
        red_bull = self.products.get_product("red-bull-original")
        recall = red_bull_openfda_recall()
        self.repository.upsert_recall(attach_match(red_bull, recall) if red_bull else recall)

    def refresh_sources(self) -> list[RegulatorySource]:
        """Refresh the known primary-source corpus independently per source."""
        RegulatorySourceIngestor(self.repository).refresh_all()
        seed_regulatory_evidence(self.repository.database)
        self.evaluate_catalog()
        return self.repository.list_sources()

    def list_discoveries(self) -> list[RegulatoryDiscovery]:
        """Expose a small, current set of source-backed homepage discoveries."""
        return build_regulatory_discoveries(self.repository, self.products)

    def evaluate_product(self, product: ProductRecord) -> list[RegulatoryFinding]:
        """Evaluate every eligible rule against the active snapshot."""
        if product.active_snapshot is None:
            self.repository.replace_findings(product.id, [])
            return []
        findings: list[RegulatoryFinding] = []
        for rule in self.repository.list_rules():
            eligible_categories = {
                "caffeinated-energy-drink": {"energy_drink", "energy-drink"},
            }.get(rule.category)
            if eligible_categories is not None and product.category not in eligible_categories:
                continue
            finding = evaluate_snapshot(product.id, product.active_snapshot, rule)
            if finding:
                findings.append(finding)
        self.repository.replace_findings(product.id, findings)
        return findings

    def evaluate_catalog(self) -> list[RegulatoryFinding]:
        """Refresh deterministic findings for all currently snapshotted products."""
        findings: list[RegulatoryFinding] = []
        for summary in self.products.list_products():
            product = self.products.get_product(summary.id)
            if product:
                findings.extend(self.evaluate_product(product))
        return findings
