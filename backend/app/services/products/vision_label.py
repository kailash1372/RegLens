"""Transient vision-label enrichment that never changes canonical scraper data."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, field_validator

from app.models.product import CanonicalProductSnapshot
from app.services.llm.client import OpenRouterClient, OpenRouterError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
VISION_FIELDS = (
    "serving_size",
    "caffeine_mg",
    "calories",
    "sugar_g",
    "nutrition_facts",
    "ingredients",
    "warnings",
)
VisionField = Literal[
    "serving_size",
    "caffeine_mg",
    "calories",
    "sugar_g",
    "nutrition_facts",
    "ingredients",
    "warnings",
]

VISION_LABEL_PROMPT = """Read only the nutrition/ingredient/warning label in this image.
Return JSON matching the supplied schema exactly. Do not infer values that are not
legible. Use null for an unavailable scalar or serving_size and [] for unavailable
lists. Nutrition facts must contain only rows visible on the label. Preserve
ingredient and warning wording, but do not include claims or product marketing."""


class VisionLabelError(RuntimeError):
    """A bounded vision-label enrichment failure."""


class VisionServingSize(BaseModel):
    """Strict serving-size shape returned by the vision model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    value: float | None = Field(default=None, ge=0)
    unit: str | None = None
    ml: float | None = Field(default=None, ge=0)


class VisionNutritionFact(BaseModel):
    """Strict nutrition-label row returned by the vision model."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    value: float | None = Field(default=None, ge=0)
    unit: str | None = None
    daily_value_percent: float | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def require_nonempty_name(cls, value: str) -> str:
        """Reject whitespace-only nutrition row names."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nutrition fact name must not be blank.")
        return normalized


class VisionLabelExtraction(BaseModel):
    """Required, schema-validated fields read from a single product-label image."""

    model_config = ConfigDict(extra="forbid", strict=True)

    serving_size: VisionServingSize | None
    caffeine_mg: float | None = Field(ge=0)
    calories: float | None = Field(ge=0)
    sugar_g: float | None = Field(ge=0)
    nutrition_facts: list[VisionNutritionFact]
    ingredients: list[str]
    warnings: list[str]

    @field_validator("ingredients", "warnings")
    @classmethod
    def require_nonempty_text(cls, values: list[str]) -> list[str]:
        """Reject blank list items rather than silently changing model output."""
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("Label text entries must not be blank.")
        return normalized


class VisionLabelFillProposals(BaseModel):
    """Only missing canonical fields that have an extracted, usable replacement."""

    model_config = ConfigDict(extra="forbid")

    serving_size: VisionServingSize | None = None
    caffeine_mg: float | None = Field(default=None, ge=0)
    calories: float | None = Field(default=None, ge=0)
    sugar_g: float | None = Field(default=None, ge=0)
    nutrition_facts: list[VisionNutritionFact] | None = None
    ingredients: list[str] | None = None
    warnings: list[str] | None = None

    @property
    def fields(self) -> set[VisionField]:
        """Return precisely the fields represented by this sparse patch."""
        return set(self.model_fields_set)


class VisionLabelConflict(BaseModel):
    """A label value that differs from an existing canonical value."""

    model_config = ConfigDict(extra="forbid")

    field: VisionField
    canonical_value: Any
    extracted_value: Any


class VisionLabelProvenance(BaseModel):
    """Audit metadata that is intentionally separate from the scraper contract."""

    model_config = ConfigDict(extra="forbid")

    image_url: HttpUrl
    transport: Literal["url", "transient_download", "fixture"]
    model: str


class VisionLabelEnrichmentResult(BaseModel):
    """Validated non-mutating enrichment result for a canonical snapshot."""

    model_config = ConfigDict(extra="forbid")

    provenance: VisionLabelProvenance
    proposed_fills: VisionLabelFillProposals
    conflicts: list[VisionLabelConflict] = Field(default_factory=list)


class VisionLabelEnricher:
    """Read a first-party label through OpenRouter or a validated fixture fallback."""

    def __init__(
        self,
        client: OpenRouterClient | None = None,
        *,
        http_client: httpx.Client | None = None,
        max_image_bytes: int = MAX_IMAGE_BYTES,
    ) -> None:
        self.client = client
        self._http_client = http_client
        self.max_image_bytes = max_image_bytes

    def enrich(
        self,
        snapshot: CanonicalProductSnapshot,
        image_url: HttpUrl | str,
        *,
        download_image: bool = False,
        fallback: VisionLabelExtraction | Mapping[str, Any] | None = None,
    ) -> VisionLabelEnrichmentResult:
        """Read an allowed label image and return safe fill proposals without mutation.

        A fixture extraction is useful for local/offline operation and is always
        schema-validated before it can be used. It is also used when a configured
        OpenRouter request fails, so an upstream outage cannot make a passport
        unusable. No network request is made when OpenRouter is not configured.
        """
        try:
            parsed_image_url = HttpUrl(image_url)
        except ValidationError as error:
            raise VisionLabelError("Label image URL is invalid.") from error
        self._require_first_party_image(snapshot, parsed_image_url)
        fallback_extraction = self._validate_fallback(fallback)
        if self.client is None or not self.client.configured:
            if fallback_extraction is None:
                raise VisionLabelError(
                    "OpenRouter is not configured and no fixture label extraction is available."
                )
            return self._result_from_extraction(
                snapshot,
                parsed_image_url,
                fallback_extraction,
                transport="fixture",
                model="fixture",
            )

        image_reference = str(parsed_image_url)
        transport: Literal["url", "transient_download"] = "url"
        if download_image:
            image_reference = self._download_as_data_url(snapshot, parsed_image_url)
            transport = "transient_download"

        try:
            response = self.client.complete(
                [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_LABEL_PROMPT},
                            {"type": "image_url", "image_url": {"url": image_reference}},
                        ],
                    }
                ],
                response_format=self._response_format(),
            )
            extraction = VisionLabelExtraction.model_validate_json(response)
        except OpenRouterError as error:
            if fallback_extraction is None:
                raise VisionLabelError("OpenRouter label enrichment failed.") from error
            return self._result_from_extraction(
                snapshot,
                parsed_image_url,
                fallback_extraction,
                transport="fixture",
                model="fixture",
            )
        except ValueError as error:
            raise VisionLabelError(
                "Vision label response did not match the required schema."
            ) from error

        return self._result_from_extraction(
            snapshot, parsed_image_url, extraction, transport=transport, model=self.client.model
        )

    @staticmethod
    def _validate_fallback(
        fallback: VisionLabelExtraction | Mapping[str, Any] | None,
    ) -> VisionLabelExtraction | None:
        if fallback is None:
            return None
        try:
            return (
                fallback
                if isinstance(fallback, VisionLabelExtraction)
                else VisionLabelExtraction.model_validate(fallback)
            )
        except ValidationError as error:
            raise VisionLabelError(
                "Fixture label extraction did not match the required schema."
            ) from error

    def _result_from_extraction(
        self,
        snapshot: CanonicalProductSnapshot,
        image_url: HttpUrl,
        extraction: VisionLabelExtraction,
        *,
        transport: Literal["url", "transient_download", "fixture"],
        model: str,
    ) -> VisionLabelEnrichmentResult:
        proposals, conflicts = self._compare(snapshot, extraction)
        return VisionLabelEnrichmentResult(
            provenance=VisionLabelProvenance(
                image_url=image_url,
                transport=transport,
                model=model,
            ),
            proposed_fills=proposals,
            conflicts=conflicts,
        )

    def _response_format(self) -> Mapping[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "product_nutrition_label",
                "strict": True,
                "schema": VisionLabelExtraction.model_json_schema(),
            },
        }

    def _require_first_party_image(
        self, snapshot: CanonicalProductSnapshot, image_url: HttpUrl
    ) -> None:
        source_url = str(snapshot.source.url)
        if image_url.scheme != "https" or not self._same_registered_domain(
            source_url, str(image_url)
        ):
            raise VisionLabelError(
                "Label image URL must be HTTPS and first-party to the product source."
            )

    def _download_as_data_url(self, snapshot: CanonicalProductSnapshot, image_url: HttpUrl) -> str:
        client = self._http_client
        close_client = client is None
        if client is None:
            client = httpx.Client(timeout=20.0, follow_redirects=True)
        try:
            response = client.get(str(image_url), follow_redirects=True)
            response.raise_for_status()
            if not self._same_registered_domain(str(snapshot.source.url), str(response.url)):
                raise VisionLabelError("Label image redirect left the first-party domain.")
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if not content_type.startswith("image/"):
                raise VisionLabelError("Label image response was not an image.")
            content = response.content
            if not content or len(content) > self.max_image_bytes:
                raise VisionLabelError("Label image is empty or exceeds the allowed size.")
            encoded = base64.b64encode(content).decode("ascii")
            return f"data:{content_type};base64,{encoded}"
        except VisionLabelError:
            raise
        except httpx.HTTPError as error:
            raise VisionLabelError("Unable to download the first-party label image.") from error
        finally:
            if close_client:
                client.close()

    def _compare(
        self, snapshot: CanonicalProductSnapshot, extraction: VisionLabelExtraction
    ) -> tuple[VisionLabelFillProposals, list[VisionLabelConflict]]:
        values: dict[str, Any] = {}
        conflicts: list[VisionLabelConflict] = []
        canonical = snapshot.model_dump(mode="json")
        extracted = extraction.model_dump(mode="json")

        for field in VISION_FIELDS:
            canonical_value = canonical[field]
            extracted_value = extracted[field]
            if field == "serving_size":
                serving_proposal, serving_conflict = self._compare_serving_size(
                    canonical_value, extracted_value
                )
                if serving_proposal is not None:
                    values[field] = serving_proposal
                if serving_conflict is not None:
                    conflicts.append(serving_conflict)
                continue
            if self._is_missing(field, canonical_value):
                if not self._is_missing(field, extracted_value):
                    values[field] = getattr(extraction, field)
            elif (
                not self._is_missing(field, extracted_value) and canonical_value != extracted_value
            ):
                conflicts.append(
                    VisionLabelConflict(
                        field=field,
                        canonical_value=canonical_value,
                        extracted_value=extracted_value,
                    )
                )

        return VisionLabelFillProposals.model_validate(values), conflicts

    @staticmethod
    def _compare_serving_size(
        canonical_value: Mapping[str, Any] | None, extracted_value: Mapping[str, Any] | None
    ) -> tuple[VisionServingSize | None, VisionLabelConflict | None]:
        if not extracted_value or all(value is None for value in extracted_value.values()):
            return None, None
        existing = canonical_value or {}
        proposed_components = {
            component: extracted_value.get(component)
            for component in ("value", "unit", "ml")
            if existing.get(component) is None and extracted_value.get(component) is not None
        }
        has_conflict = any(
            existing.get(component) is not None
            and extracted_value.get(component) is not None
            and existing[component] != extracted_value[component]
            for component in ("value", "unit", "ml")
        )
        proposal = (
            VisionServingSize.model_validate(proposed_components) if proposed_components else None
        )
        conflict = (
            VisionLabelConflict(
                field="serving_size",
                canonical_value=canonical_value,
                extracted_value=extracted_value,
            )
            if has_conflict
            else None
        )
        return proposal, conflict

    @staticmethod
    def _is_missing(field: VisionField, value: Any) -> bool:
        if field in {"nutrition_facts", "ingredients", "warnings"}:
            return not value
        return value is None

    @staticmethod
    def _same_registered_domain(left_url: str, right_url: str) -> bool:
        left_host = urlparse(left_url).hostname
        right_host = urlparse(right_url).hostname
        if not left_host or not right_host:
            return False
        left_domain = VisionLabelEnricher._registered_domain(left_host)
        right_domain = VisionLabelEnricher._registered_domain(right_host)
        return left_domain == right_domain

    @staticmethod
    def _registered_domain(hostname: str) -> str:
        parts = hostname.lower().rstrip(".").split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else hostname.lower()


def apply_label_fills(
    snapshot: CanonicalProductSnapshot, result: VisionLabelEnrichmentResult
) -> CanonicalProductSnapshot:
    """Apply only sparse, non-conflicting label proposals to a snapshot.

    The enricher itself is deliberately non-mutating. Callers that want a
    derived view can use this helper; existing canonical values are never
    replaced by a label disagreement.
    """
    payload = snapshot.model_dump(mode="json")
    proposed = result.proposed_fills
    conflicted_fields = {conflict.field for conflict in result.conflicts}
    for field in proposed.fields:
        if field in conflicted_fields:
            continue
        value = getattr(proposed, field)
        if field == "serving_size":
            current = payload["serving_size"]
            proposed_size = value.model_dump(mode="json")
            payload["serving_size"] = {
                component: (
                    current.get(component)
                    if current.get(component) is not None
                    else proposed_size.get(component)
                )
                for component in ("value", "unit", "ml")
            }
        else:
            if isinstance(value, list):
                payload[field] = [
                    item.model_dump(mode="json") if isinstance(item, BaseModel) else item
                    for item in value
                ]
            else:
                payload[field] = (
                    value.model_dump(mode="json") if isinstance(value, BaseModel) else value
                )
    return CanonicalProductSnapshot.model_validate(payload)
