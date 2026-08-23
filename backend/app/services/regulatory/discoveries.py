"""Build source-backed homepage discoveries from the current evidence store."""

from __future__ import annotations

from app.models.regulatory import RegulatoryDiscovery, VerificationStatus
from app.repositories.products import ProductRepository
from app.repositories.regulatory import RegulatoryRepository


def build_regulatory_discoveries(
    regulatory: RegulatoryRepository,
    products: ProductRepository,
) -> list[RegulatoryDiscovery]:
    """Return a small impact-oriented set without promoting research leads to facts."""
    sources = {source.id: source for source in regulatory.list_sources()}
    rules = {rule.id: rule for rule in regulatory.list_rules()}
    cards: list[RegulatoryDiscovery] = []

    caffeine_source = sources.get("health-canada-caffeinated-energy-drinks")
    caffeine_rule = rules.get("ca-ced-caffeine-max-180mg-serving")
    if caffeine_source and caffeine_rule:
        above_threshold = sorted(
            finding.product_id
            for finding in regulatory.list_findings()
            if finding.rule_id == caffeine_rule.id and finding.finding_type == "exceeds_threshold"
        )
        cards.append(
            RegulatoryDiscovery(
                id="canada-caffeine-comparison",
                topic="Caffeine limits",
                title=(
                    f"{len(above_threshold)} catalog drinks are above Canada's "
                    "180 mg comparison point"
                ),
                summary=(
                    "Health Canada states that caffeinated energy drinks can contain a "
                    "maximum of 180 mg caffeine per serving. RegLens compares current U.S. "
                    "snapshots without claiming those formulations are sold in Canada."
                ),
                authority=caffeine_source.authority,
                jurisdiction=caffeine_source.jurisdiction,
                evidence_status=caffeine_rule.verification_status,
                source_title=caffeine_source.title,
                source_url=caffeine_source.source_url,
                source_retrieved_at=caffeine_source.retrieved_at,
                ask_prompt=(
                    "Which drinks in the RegLens catalog exceed the verified Canadian "
                    "caffeine threshold?"
                ),
                related_product_ids=above_threshold,
            )
        )

    children_rule = rules.get("ca-ced-under-14-guidance")
    if caffeine_source and children_rule:
        cards.append(
            RegulatoryDiscovery(
                id="canada-children-guidance",
                topic="Children and energy drinks",
                title="Below a numeric limit does not mean recommended for children",
                summary=(
                    "Health Canada separately says caffeinated energy drinks are not "
                    "recommended for those under 14. That guidance remains relevant even "
                    "when a product is below the 180 mg per-serving threshold."
                ),
                authority=caffeine_source.authority,
                jurisdiction=caffeine_source.jurisdiction,
                evidence_status=children_rule.verification_status,
                source_title=caffeine_source.title,
                source_url=caffeine_source.source_url,
                source_retrieved_at=caffeine_source.retrieved_at,
                ask_prompt="Is Red Bull okay for children to drink?",
            )
        )

    red_three_source = sources.get("fda-fdc-red-no-3")
    if red_three_source:
        cards.append(
            RegulatoryDiscovery(
                id="fda-red-three-status-change",
                topic="Color additive status",
                title="FDA revoked authorization for FD&C Red No. 3 in food",
                summary=(
                    "FDA gives food manufacturers until January 15, 2027 to reformulate. "
                    "RegLens does not attach this event to a product unless its current "
                    "first-party ingredient list names the additive."
                ),
                authority=red_three_source.authority,
                jurisdiction=red_three_source.jurisdiction,
                evidence_status=VerificationStatus.SUPPORTED,
                source_title=red_three_source.title,
                source_url=red_three_source.source_url,
                source_retrieved_at=red_three_source.retrieved_at,
                ask_prompt="What official evidence does RegLens have about FD&C Red No. 3?",
            )
        )

    red_bull_recalls = regulatory.list_recalls("red-bull-original")
    if red_bull_recalls:
        recall = red_bull_recalls[0]
        cards.append(
            RegulatoryDiscovery(
                id="recall-match-specificity",
                topic="Recall intelligence",
                title="A recall match can be narrower than an entire brand",
                summary=(
                    "RegLens found an official FDA enforcement record for a Red Bull Energy "
                    "Drink product family. It is labelled product-family context rather than "
                    "silently attributed to every current Red Bull SKU."
                ),
                authority=recall.authority,
                jurisdiction=recall.jurisdiction,
                evidence_status=VerificationStatus.SUPPORTED,
                source_title="FDA Food Enforcement record 81503",
                source_url=recall.source_url,
                source_retrieved_at=recall.retrieved_at,
                ask_prompt="Has Red Bull appeared in official recall or enforcement data?",
                related_product_ids=[
                    product_id
                    for product_id in [recall.matched_product_id]
                    if product_id and products.get_product(product_id)
                ],
            )
        )

    return cards
