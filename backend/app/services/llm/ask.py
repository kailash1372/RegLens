"""Two-stage query understanding and evidence-grounded synthesis."""

from __future__ import annotations

import json
import re

from app.models.ask import AskProductFact, AskResult, ChatHistoryMessage, QueryIntent
from app.models.product import ProductRecord
from app.models.regulatory import RecallRecord, RegulatoryFinding, RegulatoryRule, RegulatorySource
from app.repositories.products import ProductRepository
from app.repositories.regulatory import RegulatoryRepository
from app.services.llm.client import OpenRouterClient, OpenRouterError
from app.services.retrieval.fts import RegulatoryRetriever, RetrievedPassage


class AskService:
    """Keep LLM interpretation subordinate to stored facts and deterministic rules."""

    def __init__(
        self,
        products: ProductRepository,
        regulatory: RegulatoryRepository,
        retriever: RegulatoryRetriever,
        client: OpenRouterClient | None = None,
    ) -> None:
        self.products = products
        self.regulatory = regulatory
        self.retriever = retriever
        self.client = client

    def ask(
        self,
        question: str,
        *,
        history: list[ChatHistoryMessage] | None = None,
        context_product_ids: list[str] | None = None,
    ) -> AskResult:
        """Answer with relevant snapshots, findings, recalls, and source provenance."""
        conversation = (history or [])[-12:]
        intent = self._understand(question, conversation)
        selected = self._resolve_products(
            intent,
            question,
            context_product_ids or [],
        )
        catalog_metric_question = _is_catalog_metric_question(question)
        passages = (
            []
            if catalog_metric_question
            else self.retriever.search(
                " ".join(intent.topics) or question,
                jurisdictions=intent.jurisdictions,
                topics=intent.topics,
            )
        )
        rules = self.regulatory.list_rules()
        sources = self.regulatory.list_sources()
        findings = (
            []
            if catalog_metric_question
            else [
                finding
                for product in selected
                for finding in self.regulatory.list_findings(product.id)
            ]
        )
        recalls = (
            []
            if catalog_metric_question
            else [
                recall
                for product in selected
                for recall in self.regulatory.list_recalls(product.id)
            ]
        )
        include_rule_sources = any(
            topic in {"children", "threshold", "regulatory"} for topic in intent.topics
        )
        evidence = self._evidence(
            passages,
            sources,
            rules,
            include_rule_sources=include_rule_sources,
            jurisdictions=intent.jurisdictions,
        )
        packet = self._packet(
            question,
            intent,
            selected,
            findings,
            recalls,
            evidence,
            conversation,
        )
        synthesized = None if catalog_metric_question else self._synthesize(question, packet)
        answer = synthesized or self._deterministic_answer(
            question,
            intent.topics,
            selected,
            findings,
            recalls,
            evidence,
        )
        return AskResult(
            answer=answer,
            sources=list(dict.fromkeys(item["url"] for item in evidence if item.get("url"))),
            products=[product.id for product in selected],
            product_facts=self._product_facts(selected),
            intent=intent,
            evidence=evidence,
            findings=[finding.model_dump(mode="json") for finding in findings],
            recalls=[recall.model_dump(mode="json") for recall in recalls],
            answer_mode="openrouter" if synthesized else "deterministic",
            model=self.client.model if synthesized and self.client else None,
        )

    @staticmethod
    def _product_facts(products: list[ProductRecord]) -> list[AskProductFact]:
        """Expose selected snapshot facts as structured manufacturer evidence."""
        facts: list[AskProductFact] = []
        for product in products:
            snapshot = product.active_snapshot
            if snapshot is None:
                continue
            facts.append(
                AskProductFact(
                    product_id=product.id,
                    display_name=product.display_name,
                    manufacturer=product.manufacturer,
                    market=snapshot.source.market,
                    source_url=str(snapshot.source.url),
                    scraped_at=snapshot.source.scraped_at,
                    caffeine_mg=snapshot.caffeine_mg,
                    sugar_g=snapshot.sugar_g,
                    calories=snapshot.calories,
                    serving_size=snapshot.serving_size,
                )
            )
        return facts

    def _understand(
        self,
        question: str,
        history: list[ChatHistoryMessage],
    ) -> QueryIntent:
        fallback = self._fallback_intent(question)
        if fallback.topics == ["regulatory"]:
            for message in reversed(history):
                if message.role != "user":
                    continue
                previous = self._fallback_intent(message.content)
                if previous.topics != ["regulatory"]:
                    fallback = fallback.model_copy(
                        update={
                            "topics": previous.topics,
                            "jurisdictions": previous.jurisdictions,
                        }
                    )
                    break
        known_product_mentioned = any(
            product is not None and _mentions_product(question, product)
            for product in (
                self.products.get_product(summary.id) for summary in self.products.list_products()
            )
        )
        if fallback.topics != ["regulatory"] or known_product_mentioned:
            return fallback
        if not self.client or not self.client.configured:
            return fallback
        prompt = (
            "Extract JSON only with keys intent, products, topics, jurisdictions. "
            "Use product names or brands from the question; never invent products. "
            "The intent is product_regulatory_question. Use prior conversation only to "
            "resolve follow-up references. Prior conversation: "
            + json.dumps([message.model_dump() for message in history])
            + " Question: "
            + question
        )
        try:
            content = self.client.complete(
                [
                    {"role": "system", "content": "You are a strict query parser."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
            )
            return parse_intent_json(content, fallback)
        except OpenRouterError:
            return fallback

    def _fallback_intent(self, question: str) -> QueryIntent:
        lower = question.lower()
        topics = [
            topic
            for term, topic in (
                ("caffeine", "caffeine"),
                ("children", "children"),
                ("under 14", "children"),
                ("sugar", "sugar"),
                ("ingredient", "ingredients"),
                ("recall", "recall"),
                ("exceed", "threshold"),
                ("threshold", "threshold"),
                ("least", "comparison"),
                ("lowest", "comparison"),
                ("compare", "comparison"),
            )
            if term in lower
        ]
        jurisdiction_terms = {
            "CA": ("canada", "canadian"),
            "EU": ("europe", "european union", " eu "),
            "SA": ("saudi arabia", "saudi"),
            "IN": ("india", "indian"),
            "US": ("united states", "u s formulation", "american formulation"),
        }
        jurisdictions = [
            jurisdiction
            for jurisdiction, terms in jurisdiction_terms.items()
            if any(term in lower for term in terms)
        ] or ["US", "CA"]
        return QueryIntent(
            products=[],
            topics=list(dict.fromkeys(topics or ["regulatory"])),
            jurisdictions=jurisdictions,
        )

    def _resolve_products(
        self,
        intent: QueryIntent,
        question: str,
        context_product_ids: list[str],
    ) -> list[ProductRecord]:
        all_products = [
            self.products.get_product(summary.id) for summary in self.products.list_products()
        ]
        all_products = [product for product in all_products if product]
        terms = " ".join(intent.products) or question
        selected = [product for product in all_products if _mentions_product(terms, product)]
        if selected:
            return _filter_explicit_market(selected, question)
        if _asks_about_market_formulations(question):
            family_counts: dict[str, int] = {}
            for product in all_products:
                if product.canonical_family:
                    family_counts[product.canonical_family] = (
                        family_counts.get(product.canonical_family, 0) + 1
                    )
            return [
                product
                for product in all_products
                if product.canonical_family and family_counts[product.canonical_family] > 1
            ]
        if any(
            word in question.lower() for word in ("which", "catalog", "our drinks", "these brands")
        ):
            return all_products
        context_ids = set(context_product_ids)
        contextual = [product for product in all_products if product.id in context_ids]
        if contextual:
            return contextual
        return []

    def _evidence(
        self,
        passages: list[RetrievedPassage],
        sources: list[RegulatorySource],
        rules: list[RegulatoryRule],
        *,
        include_rule_sources: bool,
        jurisdictions: list[str],
    ) -> list[dict[str, str]]:
        source_by_id = {source.id: source for source in sources}
        evidence: list[dict[str, str]] = []
        for passage in passages:
            evidence.append(
                {
                    "source_id": passage.source_id,
                    "title": passage.title,
                    "authority": passage.authority,
                    "jurisdiction": passage.jurisdiction,
                    "url": passage.source_url,
                    "text": passage.evidence_text,
                }
            )
        for rule in rules if include_rule_sources else []:
            source = source_by_id.get(rule.source_id)
            if (
                not source
                or source.jurisdiction.upper() not in {item.upper() for item in jurisdictions}
                or source.status.value != "current"
                or any(item["source_id"] == source.id for item in evidence)
            ):
                continue
            evidence.append(
                {
                    "source_id": source.id,
                    "title": source.title,
                    "authority": source.authority,
                    "jurisdiction": source.jurisdiction,
                    "url": str(source.source_url),
                    "text": rule.evidence_excerpt,
                }
            )
        return evidence

    @staticmethod
    def _packet(
        question,
        intent,
        products,
        findings,
        recalls,
        evidence,
        history,
    ) -> dict[str, object]:
        return {
            "question": question,
            "intent": intent.model_dump(),
            "products": [_compact_product(product, intent.topics) for product in products],
            "findings": [finding.model_dump(mode="json") for finding in findings],
            "recalls": [recall.model_dump(mode="json") for recall in recalls],
            "evidence": evidence,
            "conversation_history": [message.model_dump() for message in history],
        }

    def _synthesize(self, question: str, packet: dict[str, object]) -> str | None:
        if not self.client or not self.client.configured:
            return None
        system = (
            "Answer concisely, in no more than three short paragraphs, only from the supplied "
            "JSON evidence. Distinguish manufacturer facts, "
            "verified deterministic findings, and regulator guidance. Never diagnose or say "
            "a product is safe/unsafe. Do not turn a U.S. formulation comparison into a legal "
            "conclusion in Canada. Cite evidence as [source_id]."
        )
        try:
            answer = self.client.complete(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(packet)},
                ],
                max_tokens=900,
            )
            return answer if _has_supported_citations(answer, packet) else None
        except OpenRouterError:
            return None

    @staticmethod
    def _deterministic_answer(
        question: str,
        topics: list[str],
        products: list[ProductRecord],
        findings: list[RegulatoryFinding],
        recalls: list[RecallRecord],
        evidence: list[dict[str, str]],
    ) -> str:
        """Provide a useful offline answer without making an unsupported health claim."""
        lower = question.lower()
        citations = " ".join(f"[{item['source_id']}]" for item in evidence)
        if _is_catalog_metric_question(question):
            ranked = sorted(
                (
                    (product, product.active_snapshot.caffeine_mg)
                    for product in products
                    if product.active_snapshot and product.active_snapshot.caffeine_mg is not None
                ),
                key=lambda item: item[1],
            )
            if not ranked:
                return "No selected product has a stated caffeine value in its current snapshot."
            minimum = ranked[0][1]
            least = [product.display_name for product, value in ranked if value == minimum]
            ranking = "; ".join(
                f"{product.display_name}: {value:g} mg" for product, value in ranked
            )
            return (
                f"The lowest stated caffeine value is {minimum:g} mg per serving: "
                f"{', '.join(least)}. Current catalog ranking: {ranking}. This is computed "
                "from the latest stored manufacturer snapshots."
            )
        if "comparison" in topics and products:
            comparisons = []
            for product in products:
                snapshot = product.active_snapshot
                if snapshot is None:
                    continue
                serving = snapshot.serving_size
                serving_text = (
                    f"{serving.value:g} {serving.unit or ''}".strip()
                    if serving.value is not None
                    else "unstated serving"
                )
                comparisons.append(
                    f"{product.display_name} ({snapshot.source.market}, {serving_text}): "
                    f"{_metric_text(snapshot.caffeine_mg, 'mg caffeine')}, "
                    f"{_metric_text(snapshot.sugar_g, 'g sugar')}, and "
                    f"{_metric_text(snapshot.calories, 'calories')}"
                )
            return (
                "Current manufacturer-label comparison: "
                + "; ".join(comparisons)
                + ". Serving bases differ, so these values should not be compared as equal "
                "quantities unless normalized explicitly."
            )
        if "exceed" in lower or "threshold" in lower:
            names = [
                product.display_name
                for product in products
                if any(
                    item.product_id == product.id and item.finding_type == "exceeds_threshold"
                    for item in findings
                )
            ]
            if names:
                return (
                    "Products above the verified Canadian per-serving caffeine threshold: "
                    + ", ".join(names)
                    + ". "
                    + citations
                )
            return (
                "No selected product has a finding above the verified Canadian per-serving "
                "threshold. " + citations
            )
        if "recall" in lower:
            if recalls:
                return (
                    "Official enforcement context matched to the selected product family: "
                    + "; ".join(
                        f"{recall.product_description} "
                        f"({recall.classification_status or 'status not stated'})"
                        for recall in recalls
                    )
                    + ". This is historical enforcement data, not a conclusion about every "
                    "current SKU. " + citations
                )
            return (
                "No cautiously matched official recall record is stored for the selected product. "
                + citations
            )
        if "children" in topics or any(term in lower for term in ("children", "under 14")):
            product_facts = []
            for product in products:
                snapshot = product.active_snapshot
                if snapshot and snapshot.caffeine_mg is not None:
                    product_facts.append(
                        f"{product.display_name}'s current U.S. snapshot lists "
                        f"{snapshot.caffeine_mg:g} mg caffeine per serving."
                    )
            return (
                "RegLens cannot determine whether a product is appropriate for a child. "
                + (" ".join(product_facts) + " " if product_facts else "")
                + "Health Canada guidance says caffeinated energy drinks are not recommended "
                "for those under 14; this is Canadian guidance and does not establish the "
                "formulation or legal status of a U.S. product. " + citations
            )
        if products:
            facts = []
            for product in products:
                snapshot = product.active_snapshot
                if snapshot:
                    facts.append(
                        f"{product.display_name}: {snapshot.caffeine_mg:g} mg caffeine per serving"
                        if snapshot.caffeine_mg is not None
                        else f"{product.display_name}: caffeine not stated"
                    )
            return (
                "Stored manufacturer snapshot facts: "
                + "; ".join(facts)
                + ". Regulatory context is shown with provenance. "
                + citations
            )
        return (
            "I could not resolve a catalog product from that question. Ask about a named "
            "RegLens product or the catalog."
        )


def parse_intent_json(content: str, fallback: QueryIntent) -> QueryIntent:
    """Parse fenced, surrounded, or plain JSON and safely fall back when malformed."""
    candidate = content.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            return fallback
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return fallback
    try:
        return QueryIntent.model_validate(value)
    except (TypeError, ValueError):
        return fallback


def _mentions_product(text: str, product: ProductRecord) -> bool:
    normalized = _normalize_search_text(text)
    snapshot = product.active_snapshot
    aliases = {
        product.id.replace("-", " "),
        product.display_name,
        product.manufacturer,
        snapshot.brand if snapshot else None,
        snapshot.product_name if snapshot else None,
        snapshot.product_line if snapshot else None,
    }
    normalized_aliases = {
        _normalize_search_text(alias) for alias in aliases if alias and alias.strip()
    }
    return any(alias and alias in normalized for alias in normalized_aliases)


def _filter_explicit_market(
    products: list[ProductRecord],
    question: str,
) -> list[ProductRecord]:
    """Disambiguate a product family only when the user names a market."""
    normalized = _normalize_search_text(question)
    market_terms = {
        "CA": ("canada", "canadian"),
        "EU": ("europe", "european union", " eu "),
        "SA": ("saudi arabia", "saudi"),
        "IN": ("india", "indian"),
        "US": ("united states", "u s formulation", "american formulation"),
    }
    requested = {
        market
        for market, terms in market_terms.items()
        if any(term in normalized for term in terms)
    }
    if not requested:
        return products
    filtered = [product for product in products if product.market.upper() in requested]
    return filtered or products


def _asks_about_market_formulations(question: str) -> bool:
    """Recognize catalog questions about product families sold in multiple markets."""
    lower = f" {question.casefold()} "
    return "formulation" in lower and any(
        term in lower for term in ("market", "countr", "differ", "same product")
    )


def _normalize_search_text(value: str) -> str:
    """Normalize punctuation consistently on questions and product aliases."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", value.casefold())).strip()


def _compact_product(product: ProductRecord, topics: list[str]) -> dict[str, object]:
    """Send only source-grounded facts needed for synthesis, not the full database record."""
    snapshot = product.active_snapshot
    if snapshot is None:
        return {
            "id": product.id,
            "display_name": product.display_name,
            "market": product.market,
            "snapshot": None,
        }
    facts: dict[str, object] = {
        "brand": snapshot.brand,
        "product_name": snapshot.product_name,
        "flavor": snapshot.flavor,
        "serving_size": snapshot.serving_size.model_dump(),
        "caffeine_mg": snapshot.caffeine_mg,
        "calories": snapshot.calories,
        "sugar_g": snapshot.sugar_g,
        "warnings": snapshot.warnings,
        "claims": snapshot.claims,
        "source": snapshot.source.model_dump(mode="json"),
    }
    if any(topic in {"ingredients", "regulatory"} for topic in topics):
        facts["ingredients"] = snapshot.ingredients
    return {
        "id": product.id,
        "display_name": product.display_name,
        "manufacturer": product.manufacturer,
        "category": product.category,
        "market": product.market,
        "facts": facts,
    }


def _metric_text(value: float | None, label: str) -> str:
    """Render an explicit unavailable value for deterministic comparisons."""
    return f"{value:g} {label}" if value is not None else f"{label} not stated"


def _is_catalog_metric_question(question: str) -> bool:
    """Recognize deterministic catalog ranking questions without using an LLM."""
    lower = question.lower()
    return "caffeine" in lower and any(
        term in lower for term in ("least", "lowest", "minimum", "smallest")
    )


def _has_supported_citations(answer: str, packet: dict[str, object]) -> bool:
    """Accept LLM prose only when every evidence citation names a supplied source."""
    evidence = packet.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    allowed = {
        item.get("source_id")
        for item in evidence
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    cited = set(re.findall(r"\[([A-Za-z0-9][A-Za-z0-9_.:-]*)\]", answer))
    if not allowed:
        return not cited
    return bool(cited) and cited.issubset(allowed)
