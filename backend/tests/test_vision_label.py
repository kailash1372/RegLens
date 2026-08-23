"""Vision-label enrichment is schema-bound, transient, and non-mutating."""

from __future__ import annotations

import json

import httpx
import pytest
from app.models.product import CanonicalProductSnapshot
from app.services.llm.client import OpenRouterClient
from app.services.products.vision_label import (
    VisionLabelEnricher,
    VisionLabelError,
    apply_label_fills,
)


def _snapshot(**overrides: object) -> CanonicalProductSnapshot:
    payload: dict[str, object] = {
        "brand": "Red Bull",
        "product_name": "Red Bull Energy Drink",
        "serving_size": {},
        "caffeine_mg": None,
        "calories": None,
        "sugar_g": None,
        "nutrition_facts": [],
        "ingredients": [],
        "warnings": [],
        "source": {
            "url": "https://www.redbull.com/us-en/energydrink/red-bull-energy-drink",
            "market": "US",
            "scraped_at": "2026-08-23T00:00:00Z",
        },
    }
    payload.update(overrides)
    return CanonicalProductSnapshot.model_validate(payload)


def _label_response(**overrides: object) -> str:
    payload: dict[str, object] = {
        "serving_size": {"value": 8.4, "unit": "fl oz", "ml": 248.0},
        "caffeine_mg": 80.0,
        "calories": 110.0,
        "sugar_g": 27.0,
        "nutrition_facts": [
            {"name": "Sodium", "value": 105.0, "unit": "mg", "daily_value_percent": 5.0}
        ],
        "ingredients": ["Water", "Sugar"],
        "warnings": ["Not recommended for children."],
    }
    payload.update(overrides)
    return json.dumps(payload)


def _openrouter_client(handler: httpx.MockTransport) -> tuple[OpenRouterClient, httpx.Client]:
    client = httpx.Client(transport=handler)
    return OpenRouterClient("test-key", http_client=client), client


def test_enricher_proposes_only_missing_canonical_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body["messages"][0]["content"]
        assert content[1]["image_url"]["url"] == "https://images.redbull.com/labels/original.png"
        assert body["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _label_response()}}]},
            request=request,
        )

    llm, client = _openrouter_client(httpx.MockTransport(handler))
    try:
        snapshot = _snapshot()
        result = VisionLabelEnricher(llm).enrich(
            snapshot, "https://images.redbull.com/labels/original.png"
        )
    finally:
        client.close()

    assert result.proposed_fills.fields == {
        "serving_size",
        "caffeine_mg",
        "calories",
        "sugar_g",
        "nutrition_facts",
        "ingredients",
        "warnings",
    }
    assert result.proposed_fills.caffeine_mg == 80.0
    assert result.conflicts == []
    assert snapshot.caffeine_mg is None
    assert result.provenance.transport == "url"


def test_enricher_flags_conflicts_without_proposing_overwrites() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _label_response()}}]},
            request=request,
        )

    llm, client = _openrouter_client(httpx.MockTransport(handler))
    try:
        snapshot = _snapshot(caffeine_mg=75.0, ingredients=["Carbonated water"])
        result = VisionLabelEnricher(llm).enrich(
            snapshot, "https://images.redbull.com/labels/original.png"
        )
    finally:
        client.close()

    assert "caffeine_mg" not in result.proposed_fills.fields
    assert "ingredients" not in result.proposed_fills.fields
    assert {conflict.field for conflict in result.conflicts} == {"caffeine_mg", "ingredients"}
    assert snapshot.caffeine_mg == 75.0
    assert snapshot.ingredients == ["Carbonated water"]


def test_enricher_proposes_only_missing_serving_components_and_flags_difference() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": _label_response(
                                serving_size={"value": 7.5, "unit": "fl oz", "ml": 222.0}
                            )
                        }
                    }
                ]
            },
            request=request,
        )

    llm, client = _openrouter_client(httpx.MockTransport(handler))
    try:
        result = VisionLabelEnricher(llm).enrich(
            _snapshot(serving_size={"value": 8.4}),
            "https://images.redbull.com/labels/original.png",
        )
    finally:
        client.close()

    assert result.proposed_fills.serving_size is not None
    assert result.proposed_fills.serving_size.value is None
    assert result.proposed_fills.serving_size.unit == "fl oz"
    assert result.proposed_fills.serving_size.ml == 222.0
    assert [conflict.field for conflict in result.conflicts] == ["serving_size"]


def test_enricher_rejects_invalid_structured_output() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"calories": 110.0}'}}]},
            request=request,
        )

    llm, client = _openrouter_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(VisionLabelError, match="required schema"):
            VisionLabelEnricher(llm).enrich(
                _snapshot(), "https://images.redbull.com/labels/original.png"
            )
    finally:
        client.close()


def test_download_fallback_is_transient_and_never_exposed_in_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "images.redbull.com":
            return httpx.Response(
                200,
                content=b"\x89PNG\r\n",
                headers={"content-type": "image/png"},
                request=request,
            )
        body = json.loads(request.content)
        image_reference = body["messages"][0]["content"][1]["image_url"]["url"]
        assert image_reference == "data:image/png;base64,iVBORw0K"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": _label_response()}}]},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    llm = OpenRouterClient("test-key", http_client=http_client)
    try:
        result = VisionLabelEnricher(llm, http_client=http_client).enrich(
            _snapshot(),
            "https://images.redbull.com/labels/original.png",
            download_image=True,
        )
    finally:
        http_client.close()

    assert result.provenance.transport == "transient_download"
    serialized = result.model_dump_json()
    assert "data:image" not in serialized
    assert "iVBORw0K" not in serialized


def test_enricher_rejects_non_first_party_images_before_llm_call() -> None:
    llm = OpenRouterClient("test-key")
    with pytest.raises(VisionLabelError, match="first-party"):
        VisionLabelEnricher(llm).enrich(
            _snapshot(), "https://images.example.com/labels/original.png"
        )


def test_unconfigured_enricher_uses_validated_fixture_fallback() -> None:
    result = VisionLabelEnricher().enrich(
        _snapshot(),
        "https://images.redbull.com/labels/original.png",
        fallback=json.loads(_label_response()),
    )

    assert result.provenance.transport == "fixture"
    assert result.provenance.model == "fixture"
    enriched = apply_label_fills(_snapshot(), result)
    assert enriched.caffeine_mg == 80
    assert enriched.serving_size.ml == 248
    assert enriched.ingredients == ["Water", "Sugar"]


def test_openrouter_failure_falls_back_without_overwriting_canonical_values() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    llm = OpenRouterClient("test-key", http_client=http_client)
    try:
        result = VisionLabelEnricher(llm).enrich(
            _snapshot(caffeine_mg=75),
            "https://images.redbull.com/labels/original.png",
            fallback=json.loads(_label_response()),
        )
    finally:
        http_client.close()

    enriched = apply_label_fills(_snapshot(caffeine_mg=75), result)
    assert result.provenance.transport == "fixture"
    assert enriched.caffeine_mg == 75
    assert any(conflict.field == "caffeine_mg" for conflict in result.conflicts)
