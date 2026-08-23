"""Authoritative regulatory source ingestion with last-known-good preservation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser

import httpx

from app.models.regulatory import RegulatorySource
from app.repositories.regulatory import RegulatoryRepository


class RegulatorySourceRefreshError(RuntimeError):
    """One authoritative source could not be retrieved or parsed safely."""


@dataclass(frozen=True)
class RegulatorySourceDefinition:
    """Stable provenance and the preserved content shipped for offline use."""

    id: str
    authority: str
    jurisdiction: str
    title: str
    source_url: str
    source_type: str
    preserved_content: str
    evidence_text: str
    evidence_anchor: str | None = None


CORPUS_RETRIEVED_AT = datetime(2026, 8, 23, tzinfo=UTC)

SOURCE_DEFINITIONS = (
    RegulatorySourceDefinition(
        id="health-canada-caffeinated-energy-drinks",
        authority="Health Canada",
        jurisdiction="CA",
        title="Caffeinated energy drinks: what you should know",
        source_url=(
            "https://recalls-rappels.canada.ca/en/alert-recall/"
            "caffeinated-energy-drinks-what-you-should-know"
        ),
        source_type="government-guidance",
        preserved_content=(
            "In Canada, CEDs can contain a maximum of 180 mg of caffeine per serving. "
            "CEDs are not recommended for those under 14 years old, those who are "
            "pregnant or breastfeeding, or people sensitive to caffeine."
        ),
        evidence_text=(
            "In Canada, CEDs can contain a maximum of 180 mg of caffeine per serving. "
            "CEDs are not recommended for those under 14 years old, those who are "
            "pregnant or breastfeeding, or people sensitive to caffeine."
        ),
        evidence_anchor="In Canada, CEDs can contain a maximum of 180 mg of caffeine per serving.",
    ),
    RegulatorySourceDefinition(
        id="health-canada-permitted-supplemental-ingredients",
        authority="Health Canada",
        jurisdiction="CA",
        title="List of Permitted Supplemental Ingredients",
        source_url=(
            "https://www.canada.ca/en/health-canada/services/food-nutrition/"
            "supplemented-foods/list-permitted-food-ingredients.html"
        ),
        source_type="incorporated-by-reference-list",
        preserved_content=(
            "The List of Permitted Supplemental Ingredients is incorporated by reference "
            "in the Food and Drug Regulations. It lists supplemental ingredients permitted "
            "for addition to supplemented foods and their conditions of use, including food "
            "categories, maximum amounts per serving, cautionary statements, and additional "
            "labelling requirements."
        ),
        evidence_text=(
            "Health Canada's incorporated-by-reference list of permitted supplemental "
            "ingredients and their conditions of use."
        ),
        evidence_anchor=(
            "The List of Permitted Supplemental Ingredients is incorporated by reference"
        ),
    ),
    RegulatorySourceDefinition(
        id="fda-color-additives",
        authority="U.S. Food and Drug Administration",
        jurisdiction="US",
        title="Color Additives",
        source_url="https://www.fda.gov/industry/color-additives",
        source_type="regulatory-information",
        preserved_content=(
            "Under the Federal Food, Drug, and Cosmetic Act, color additives, except for "
            "coal tar hair dyes, are subject to FDA approval before they may be used in food, "
            "drugs, cosmetics, or certain medical devices. FDA provides inventories and "
            "regulatory resources describing approved uses, specifications, restrictions, "
            "and certification requirements."
        ),
        evidence_text=(
            "FDA regulatory information and inventories for color-additive approval, "
            "permitted uses, restrictions, and certification."
        ),
        evidence_anchor="are subject to FDA approval before they may be used in food",
    ),
    RegulatorySourceDefinition(
        id="fda-fdc-red-no-3",
        authority="U.S. Food and Drug Administration",
        jurisdiction="US",
        title="FD&C Red No. 3",
        source_url="https://www.fda.gov/industry/color-additives/fdc-red-no-3",
        source_type="regulatory-action",
        preserved_content=(
            "On January 15, 2025, FDA issued an order to revoke the authorizations "
            "for the use of FD&C Red No. 3 in food and ingested drugs. Manufacturers "
            "who use FD&C Red No. 3 in food have until January 15, 2027 to reformulate "
            "their products; manufacturers of ingested drugs have until January 18, "
            "2028. Products containing the color additive that were manufactured before "
            "the applicable deadline may remain on the market after that date."
        ),
        evidence_text=(
            "FDA revoked the authorizations for FD&C Red No. 3 in food and ingested "
            "drugs, with a January 15, 2027 food-manufacturer reformulation deadline."
        ),
        evidence_anchor="On January 15, 2025, FDA issued an order to revoke the authorizations",
    ),
    RegulatorySourceDefinition(
        id="canada-recalls-open-data",
        authority="Health Canada",
        jurisdiction="CA",
        title="Recalls and Safety Alerts",
        source_url=("https://open.canada.ca/data/en/dataset/d38de914-c94c-429b-8ab1-8776c31643e3"),
        source_type="official-open-data",
        preserved_content=(
            "The Recalls and Safety Alerts website is the official Government of Canada "
            "centralized website for recalls and safety alerts related to food, consumer "
            "products, health products, medical devices, cannabis, and vehicles sold in "
            "Canada. The open dataset is updated daily for use by third-party platforms."
        ),
        evidence_text=(
            "Government of Canada metadata for the official, daily-updated Recalls and "
            "Safety Alerts open dataset."
        ),
        evidence_anchor=(
            "official Government of Canada centralized website for recalls and safety alerts"
        ),
    ),
)


class _ReadableTextParser(HTMLParser):
    """Extract readable page text while excluding executable and styling content."""

    ignored_tags = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.fragments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in self.ignored_tags:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = " ".join(data.split())
        if text:
            self.fragments.append(text)

    def content(self) -> str:
        """Return normalized text while collapsing adjacent duplicate fragments."""
        unique: list[str] = []
        for fragment in self.fragments:
            if not unique or unique[-1] != fragment:
                unique.append(fragment)
        return "\n".join(unique)


class RegulatorySourceIngestor:
    """Refresh known primary sources without replacing good content on failure."""

    def __init__(
        self,
        repository: RegulatoryRepository,
        client: httpx.Client | None = None,
    ) -> None:
        self.repository = repository
        self.client = client

    def refresh_all(self) -> list[RegulatorySource]:
        """Refresh each configured source independently and return current records."""
        for definition in SOURCE_DEFINITIONS:
            self.refresh(definition.id)
        return self.repository.list_sources()

    def refresh(self, source_id: str) -> RegulatorySource:
        """Retrieve one exact configured URL and persist only usable page content."""
        definition = next(
            (item for item in SOURCE_DEFINITIONS if item.id == source_id),
            None,
        )
        if definition is None:
            raise KeyError(source_id)
        try:
            content = self._retrieve(definition)
        except RegulatorySourceRefreshError as error:
            self.repository.record_source_refresh_failure(source_id, str(error))
            current = next(
                (item for item in self.repository.list_sources() if item.id == source_id),
                None,
            )
            if current is None:
                raise
            return current
        if definition.evidence_anchor and not _contains_anchor(
            content,
            definition.evidence_anchor,
        ):
            self.repository.record_missing_evidence_anchor(
                source_id,
                "Authoritative source no longer contains the required evidence anchor; "
                "last-known-good evidence was retained and dependent rules need review.",
            )
            current = next(
                (item for item in self.repository.list_sources() if item.id == source_id),
                None,
            )
            if current is None:
                raise RegulatorySourceRefreshError(
                    "No last-known-good evidence exists for the missing anchor."
                )
            return current
        source = _source_from_definition(
            definition,
            content=content,
            retrieved_at=datetime.now(UTC),
        )
        self.repository.upsert_source(source)
        return source

    def _retrieve(self, definition: RegulatorySourceDefinition) -> str:
        client = self.client
        owns_client = client is None
        if client is None:
            client = httpx.Client(
                follow_redirects=True,
                timeout=httpx.Timeout(35.0),
            )
        try:
            response = client.get(definition.source_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type.lower():
                raise RegulatorySourceRefreshError(
                    "Authoritative source returned an unsupported content type."
                )
            parser = _ReadableTextParser()
            parser.feed(response.text)
            content = parser.content()
            if len(content) < 200:
                raise RegulatorySourceRefreshError(
                    "Authoritative source returned insufficient readable content."
                )
            return content
        except RegulatorySourceRefreshError:
            raise
        except httpx.HTTPError as error:
            raise RegulatorySourceRefreshError(
                f"Authoritative source refresh failed: {error.__class__.__name__}."
            ) from error
        finally:
            if owns_client:
                client.close()


def seed_regulatory_sources(repository: RegulatoryRepository) -> None:
    """Install a preserved offline corpus without overwriting newer live content."""
    existing = {source.id: source for source in repository.list_sources()}
    for definition in SOURCE_DEFINITIONS:
        current = existing.get(definition.id)
        if current is not None and current.content:
            continue
        repository.upsert_source(
            _source_from_definition(
                definition,
                content=definition.preserved_content,
                retrieved_at=CORPUS_RETRIEVED_AT,
            )
        )


def _source_from_definition(
    definition: RegulatorySourceDefinition,
    *,
    content: str,
    retrieved_at: datetime,
) -> RegulatorySource:
    return RegulatorySource(
        id=definition.id,
        authority=definition.authority,
        jurisdiction=definition.jurisdiction,
        title=definition.title,
        source_url=definition.source_url,
        retrieved_at=retrieved_at,
        source_type=definition.source_type,
        content=content,
        evidence_text=definition.evidence_text,
        evidence_anchor=definition.evidence_anchor,
        content_hash=sha256(content.encode("utf-8")).hexdigest(),
    )


def _contains_anchor(content: str, anchor: str) -> bool:
    """Compare human-readable evidence anchors despite insignificant whitespace drift."""
    return " ".join(anchor.split()).casefold() in " ".join(content.split()).casefold()
