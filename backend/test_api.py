import os
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.pop("OPENAI_API_KEY", None)

from app.main import app  # noqa: E402


client = TestClient(app)


def test_health_reports_v04_database_scale():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.4.0"
    assert body["catalogue_records"] == 101
    assert body["source_profiles"] == 1028
    assert body["countries"] == 16
    assert body["ai_parser_enabled"] is False


def test_ai_parser_is_disabled_by_default_even_when_a_key_exists():
    from app.parser import parse_meal

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
        with patch("app.parser.ai_parse") as mocked_ai_parse:
            items, parser_source, _ = parse_meal("one bowl of waakye")

    mocked_ai_parse.assert_not_called()
    assert parser_source == "fallback"
    assert items[0].canonical_key == "waakye"


def test_cors_allows_development_web_clients():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_coverage_prioritises_nigeria_and_ghana_without_excluding_region():
    response = client.get("/coverage")
    assert response.status_code == 200
    body = response.json()
    assert body["coverage_tiers"]["priority"]["countries"] == ["Nigeria", "Ghana"]
    assert body["stats"]["country_counts"]["Nigeria"] >= 70
    assert body["stats"]["country_counts"]["Ghana"] >= 70
    assert all(count > 0 for count in body["stats"]["country_counts"].values())


def test_catalogue_filters_and_exposes_recipe_provenance():
    response = client.get("/catalog", params={"country": "Nigeria", "q": "jollof"})
    assert response.status_code == 200
    assert any(food["key"] == "jollof_rice" for food in response.json())

    detail = client.get("/catalog/jollof_rice")
    assert detail.status_code == 200
    body = detail.json()
    assert body["data_quality"] == "calculated_recipe"
    assert body["recipe"]["final_weight_g"] == 1200
    assert len(body["recipe"]["ingredients"]) >= 5
    assert body["nutrients_per_100g"]["calories_kcal"] > 0


def test_natural_meal_parsing_and_provenance():
    response = client.post(
        "/analyze",
        json={
            "meal": "I had 2 scoops of egusi soup, one wrap of pounded yam and two small pieces of beef"
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [item["canonical_key"] for item in body["components"]] == [
        "egusi_soup",
        "pounded_yam",
        "stewed_beef",
    ]
    assert all(item["source_id"] == "fao_wafct_2019" for item in body["components"])
    assert body["components"][2]["grams"] == 105.0
    assert body["confidence"] == "medium"


def test_verified_gram_weight_flow():
    response = client.post("/analyze", json={"meal": "85 grams of beef"})
    assert response.status_code == 200
    body = response.json()
    assert round(body["components"][0]["grams"]) == 85
    assert body["components"][0]["data_quality"] == "verified_source"
    assert body["confidence"] == "high"


def test_ghanaian_meal_and_long_alias_overlap():
    response = client.post(
        "/analyze",
        json={"meal": "a bowl of waakye, one piece of grilled tilapia and 2 tablespoons of shito"},
    )
    assert response.status_code == 200
    keys = [item["canonical_key"] for item in response.json()["components"]]
    assert keys == ["waakye", "grilled_tilapia", "shito"]

    jollof = client.post("/analyze", json={"meal": "one cup of jollof rice"})
    assert jollof.status_code == 200
    assert [item["canonical_key"] for item in jollof.json()["components"]] == ["jollof_rice"]


def test_francophone_and_senegambian_aliases():
    response = client.post(
        "/analyze",
        json={"meal": "one plate of ceebu jën with a glass of coconut water"},
    )
    assert response.status_code == 200
    keys = [item["canonical_key"] for item in response.json()["components"]]
    assert keys == ["thieboudienne", "coconut_water"]

    response = client.post("/analyze", json={"meal": "a bowl of domoda"})
    assert response.status_code == 200
    assert response.json()["components"][0]["canonical_key"] == "groundnut_stew"


def test_no_active_development_estimates_remain():
    response = client.get("/catalog")
    assert response.status_code == 200
    assert len(response.json()) == 101
    assert all(food["data_quality"] != "development_estimate" for food in response.json())


def test_unknown_meal_returns_clear_422():
    response = client.post("/analyze", json={"meal": "a bowl of moon rocks"})
    assert response.status_code == 422
    assert "V0.4 catalogue" in response.json()["detail"]


def test_ai_structured_output_keys_are_validated_against_catalogue():
    from app.parser import AIParsedItem, AIParsedMeal, ai_parse

    class FakeResponses:
        def parse(self, **_kwargs):
            return type(
                "FakeResponse",
                (),
                {
                    "output_parsed": AIParsedMeal(
                        items=[
                            AIParsedItem(
                                raw_name="waakye",
                                canonical_key="waakye",
                                quantity=1,
                                unit="bowl",
                                size="medium",
                                notes="Clear catalogue match.",
                            ),
                            AIParsedItem(
                                raw_name="invented food",
                                canonical_key="invented_key",
                                quantity=1,
                                unit="serving",
                                size="unspecified",
                                notes="Not a real catalogue key.",
                            ),
                        ]
                    )
                },
            )()

    class FakeClient:
        responses = FakeResponses()

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("openai.OpenAI", return_value=FakeClient()):
            items = ai_parse("one bowl of waakye and invented food")

    assert len(items) == 1
    assert items[0].canonical_key == "waakye"
    assert items[0].unit == "bowl"
