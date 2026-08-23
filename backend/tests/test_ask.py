"""Offline retrieval, malformed intent handling, and LLM client tests."""

import json
from pathlib import Path

import httpx
from app.core.config import Settings
from app.db.database import Database
from app.main import create_app
from app.models.ask import QueryIntent
from app.services.llm.ask import parse_intent_json
from app.services.llm.client import OpenRouterClient
from app.services.regulatory.seed import seed_regulatory_evidence
from app.services.retrieval.fts import RegulatoryRetriever
from fastapi.testclient import TestClient


def test_fts_retrieval_keeps_source_provenance(tmp_path: Path) -> None:
    database = Database(tmp_path / "evidence.db")
    database.initialize()
    seed_regulatory_evidence(database)
    passages = RegulatoryRetriever(database).search("Canadian caffeine children")
    assert passages
    assert passages[0].source_id == "health-canada-caffeinated-energy-drinks"
    assert passages[0].authority == "Health Canada"
    assert passages[0].jurisdiction == "CA"
    assert "180 mg" in passages[0].evidence_text


def test_malformed_llm_json_falls_back_without_raising() -> None:
    fallback = QueryIntent(products=["celsius-sparkling-orange"], topics=["caffeine"])
    assert parse_intent_json("not JSON", fallback) == fallback
    assert parse_intent_json("```json\n{bad}\n```", fallback) == fallback
    parsed = parse_intent_json('{"products":["CELSIUS"],"topics":["children"]}', fallback)
    assert parsed.products == ["CELSIUS"]


def test_openrouter_client_uses_typed_chat_response_without_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenRouterClient("test-key", http_client=client)
    assert llm.complete([{"role": "user", "content": "hello"}]) == "answer"
    client.close()


def test_openrouter_client_supports_multimodal_messages_and_response_format() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["messages"] == [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "read this label"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/label.png"}},
                ],
            }
        ]
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}]},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = OpenRouterClient("test-key", http_client=client)
    assert (
        llm.complete(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "read this label"},
                        {
                            "type": "image_url",
                            "image_url": {"url": "https://example.com/label.png"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )
        == "{}"
    )
    client.close()


def test_ask_endpoint_has_safe_offline_fallback(tmp_path: Path) -> None:
    settings = Settings(
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "ask.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/ask", json={"question": "Is Celsius okay for children to drink?"}
        )
        assert response.status_code == 200
        body = response.json()
        assert "cannot determine" in body["answer"]
        assert body["evidence"]
        assert body["sources"]
        assert body["product_facts"][0]["display_name"] == "CELSIUS Sparkling Orange"
        assert body["product_facts"][0]["caffeine_mg"] == 200
        assert "celsius.com" in body["product_facts"][0]["source_url"]
        assert body["answer_mode"] == "deterministic"
        assert body["model"] is None


def test_ask_threshold_answer_is_driven_by_verified_findings(tmp_path: Path) -> None:
    """Catalog threshold answers include only products above the stored verified rule."""
    settings = Settings(
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "threshold.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/ask",
            json={
                "question": "Which drinks in our catalog exceed the verified Canadian "
                "caffeine threshold?"
            },
        )
        assert response.status_code == 200
        answer = response.json()["answer"]
        assert "CELSIUS Sparkling Orange" in answer
        assert "Alani Nu Cotton Candy Energy" in answer
        assert "C4 Performance Energy Frozen Bombsicle" in answer
        assert "Bloom Raspberry Lemon" not in answer
        assert "Red Bull Original" not in answer


def test_ask_least_caffeine_is_computed_from_catalog_snapshots(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "ranking.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/ask",
            json={"question": "Which drink has the least caffeine?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Red Bull Original Energy Drink" in body["answer"]
    assert "80 mg" in body["answer"]
    assert body["sources"] == []
    assert body["findings"] == []
    assert body["recalls"] == []


def test_ask_resolves_new_brand_and_market_variant_without_llm(tmp_path: Path) -> None:
    """Expanded products and explicit market terms resolve deterministically."""
    settings = Settings(
        _env_file=None,
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "expanded-ask.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        fanta = client.post(
            "/api/ask",
            json={"question": "What is in Fanta Orange in Canada?"},
        ).json()
        maggi = client.post(
            "/api/ask",
            json={"question": "What does the MAGGI label state?"},
        ).json()
        comparison = client.post(
            "/api/ask",
            json={"question": "Compare Fanta Orange in Canada and Saudi Arabia."},
        ).json()

    assert fanta["products"] == ["fanta-orange-ca"]
    assert fanta["product_facts"][0]["market"] == "CA"
    assert maggi["products"] == ["maggi-masala-noodles"]
    assert "500 ml" in comparison["answer"]
    assert "100 ml" in comparison["answer"]
    assert "Serving bases differ" in comparison["answer"]


def test_ask_follow_up_reuses_explicit_product_context(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "follow-up.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/ask",
            json={
                "question": "What about its caffeine?",
                "history": [
                    {"role": "user", "content": "Is Celsius okay for children?"},
                    {"role": "assistant", "content": "The product snapshot lists caffeine."},
                ],
                "context_products": ["celsius-sparkling-orange"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["products"] == ["celsius-sparkling-orange"]
    assert "200 mg" in body["answer"]


def test_ask_follow_up_changes_product_and_keeps_prior_topic(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        REGLENS_DATA_PROVIDER="fixture",
        REGLENS_DATABASE_PATH=tmp_path / "follow-up-product.db",
        OPENROUTER_API_KEY=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/ask",
            json={
                "question": "What about Red Bull?",
                "history": [
                    {"role": "user", "content": "Is Celsius okay for children?"},
                    {"role": "assistant", "content": "Health Canada guidance applies."},
                ],
                "context_products": ["celsius-sparkling-orange"],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["products"] == ["red-bull-original"]
    assert body["intent"]["topics"] == ["children"]
    assert "80 mg" in body["answer"]
    assert "under 14" in body["answer"]
    assert body["evidence"][0]["source_id"] == "health-canada-caffeinated-energy-drinks"
