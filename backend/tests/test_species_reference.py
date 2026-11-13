import asyncio
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.schemas.persona import PlantContext
from app.services.auth import AuthenticatedUser
from app.services.persona import build_system_instruction
from app.services.species_reference import (
    _compose_reference,
    fetch_plant_species_reference,
    normalize_species_query,
)

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def example_reference():
    return _compose_reference(
        "몬스테라",
        "Monstera deliciosa",
        {
            "common_name": "Swiss cheese plant",
            "scientific_name": ["Monstera deliciosa"],
            "watering": "Average",
            "sunlight": ["part shade"],
            "care_level": "Easy",
            "indoor": True,
            "cycle": "Perennial",
        },
        {
            "scientificName": "Monstera deliciosa Liebm.",
            "canonicalName": "Monstera deliciosa",
            "family": "Araceae",
            "genus": "Monstera",
            "rank": "SPECIES",
            "status": "ACCEPTED",
            "confidence": 99,
        },
    )


def test_korean_alias_is_normalized_for_external_apis():
    assert normalize_species_query(" 몬스테라 ") == "Monstera deliciosa"


def test_reference_combines_care_and_taxonomy():
    reference = example_reference()
    assert reference.watering == "Average"
    assert reference.sunlight == ["part shade"]
    assert reference.taxonomy is not None
    assert reference.taxonomy.family == "Araceae"
    assert reference.sources == ["Perenual", "GBIF"]


def test_reference_is_added_to_ai_prompt():
    plant = PlantContext(name="초록이", species="몬스테라", care_reference=example_reference())
    prompt = build_system_instruction(plant)
    assert "external_care_reference" in prompt
    assert "Monstera deliciosa" in prompt
    assert "측정값을 우선" in prompt


def test_saved_plant_reference_is_reused_without_external_lookup():
    saved = example_reference()
    settings = Settings(
        _env_file=None,
        supabase_url="https://example.supabase.co",
        supabase_anon_key="test-anon-key",
    )
    with (
        patch(
            "app.services.species_reference._load_plant_reference",
            new_callable=AsyncMock,
            return_value=saved,
        ) as load,
        patch(
            "app.services.species_reference.fetch_species_reference",
            new_callable=AsyncMock,
        ) as external,
    ):
        result = asyncio.run(
            fetch_plant_species_reference(
                "몬스테라",
                settings,
                plant_id="plant-1",
                access_token="user-token",
            )
        )
    assert result == saved
    load.assert_awaited_once()
    external.assert_not_awaited()


def test_species_reference_endpoint_requires_login():
    response = client.get("/api/species-reference", params={"q": "몬스테라"})
    assert response.status_code == 401


def test_species_reference_endpoint_returns_auxiliary_data():
    async def authenticate_user(*_args, **_kwargs):
        return AuthenticatedUser(id="user-1", email="test@plantalk.local")

    async def return_reference(*_args, **_kwargs):
        return example_reference()

    with (
        patch("app.api.routes.chat.authenticate", new=authenticate_user),
        patch(
            "app.api.routes.species_reference.fetch_plant_species_reference",
            new=return_reference,
        ),
    ):
        response = client.get(
            "/api/species-reference",
            params={"q": "몬스테라"},
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert response.json()["reference"]["watering"] == "Average"
    assert "실제 급수 판단" in response.json()["usage"]
