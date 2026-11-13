from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.schemas.persona import PlantContext
from app.schemas.species_reference import SpeciesCareReference, SpeciesTaxonomy


class SpeciesReferenceError(Exception):
    pass


KOREAN_SPECIES_ALIASES = {
    "몬스테라": "Monstera deliciosa",
    "스킨답서스": "Epipremnum aureum",
    "스투키": "Dracaena angolensis",
    "산세베리아": "Dracaena trifasciata",
    "바질": "Ocimum basilicum",
    "상추": "Lactuca sativa",
    "방울토마토": "Solanum lycopersicum",
}

CACHE_TTL_SECONDS = 24 * 60 * 60


@dataclass
class _CacheEntry:
    expires_at: float
    value: SpeciesCareReference


_cache: dict[str, _CacheEntry] = {}


def normalize_species_query(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    return KOREAN_SPECIES_ALIASES.get(cleaned.casefold(), cleaned)


def _non_blank(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _supabase_user_headers(
    settings: Settings,
    access_token: str,
    prefer: str | None = None,
) -> dict[str, str] | None:
    if not settings.supabase_url or not settings.supabase_anon_key or not access_token:
        return None
    key = settings.supabase_anon_key.get_secret_value().strip()
    if not key:
        return None
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


async def _load_plant_reference(
    client: httpx.AsyncClient,
    plant_id: str,
    normalized_query: str,
    access_token: str,
    settings: Settings,
) -> SpeciesCareReference | None:
    headers = _supabase_user_headers(settings, access_token)
    if not headers or not settings.supabase_url:
        return None
    response = await client.get(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/plants",
        headers=headers,
        params={
            "select": "extra_care",
            "id": f"eq.{plant_id}",
            "limit": "1",
        },
    )
    if response.is_error:
        return None
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        return None
    extra_care = rows[0].get("extra_care") if isinstance(rows[0], dict) else None
    raw_reference = (
        extra_care.get("external_species_reference") if isinstance(extra_care, dict) else None
    )
    if not isinstance(raw_reference, dict):
        return None
    try:
        reference = SpeciesCareReference.model_validate(raw_reference)
    except (TypeError, ValueError):
        return None
    if reference.normalized_query.casefold() != normalized_query.casefold():
        return None
    return reference


async def _save_plant_reference(
    client: httpx.AsyncClient,
    plant_id: str,
    reference: SpeciesCareReference,
    access_token: str,
    settings: Settings,
) -> bool:
    headers = _supabase_user_headers(settings, access_token)
    if not headers or not settings.supabase_url:
        return False
    lookup = await client.get(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/plants",
        headers=headers,
        params={"select": "care_overrides", "id": f"eq.{plant_id}", "limit": "1"},
    )
    if lookup.is_error:
        return False
    rows = lookup.json()
    if not isinstance(rows, list) or not rows:
        return False
    care_overrides = rows[0].get("care_overrides") if isinstance(rows[0], dict) else {}
    if not isinstance(care_overrides, dict):
        care_overrides = {}
    care_overrides["external_species_reference"] = reference.model_dump(mode="json")
    response = await client.patch(
        f"{settings.supabase_url.rstrip('/')}/rest/v1/plants",
        headers=_supabase_user_headers(settings, access_token, "return=minimal"),
        params={"id": f"eq.{plant_id}"},
        json={"care_overrides": care_overrides},
    )
    return not response.is_error


async def _fetch_perenual(
    client: httpx.AsyncClient,
    query: str,
    settings: Settings,
) -> dict[str, object] | None:
    if not settings.perenual_api_key:
        return None
    key = settings.perenual_api_key.get_secret_value().strip()
    if not key:
        return None
    response = await client.get(
        f"{settings.perenual_api_base_url.rstrip('/')}/species-list",
        params={"key": key, "q": query},
    )
    if response.status_code in (401, 403, 429):
        return None
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", []) if isinstance(payload, dict) else []
    return rows[0] if rows and isinstance(rows[0], dict) else None


async def _fetch_gbif(
    client: httpx.AsyncClient,
    query: str,
    settings: Settings,
) -> dict[str, object] | None:
    response = await client.get(
        f"{settings.gbif_api_base_url.rstrip('/')}/species/match",
        params={"name": query, "kingdom": "Plantae", "verbose": "true"},
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) and payload.get("matchType") != "NONE" else None


def _compose_reference(
    original_query: str,
    normalized_query: str,
    perenual: dict[str, object] | None,
    gbif: dict[str, object] | None,
) -> SpeciesCareReference:
    scientific_names = _strings(perenual.get("scientific_name")) if perenual else []
    taxonomy = None
    if gbif:
        taxonomy = SpeciesTaxonomy(
            scientific_name=_non_blank(gbif.get("scientificName")),
            canonical_name=_non_blank(gbif.get("canonicalName")),
            family=_non_blank(gbif.get("family")),
            genus=_non_blank(gbif.get("genus")),
            rank=_non_blank(gbif.get("rank")),
            status=_non_blank(gbif.get("status")),
            confidence=gbif.get("confidence") if isinstance(gbif.get("confidence"), int) else None,
        )
        accepted = taxonomy.canonical_name or taxonomy.scientific_name
        if accepted and accepted not in scientific_names:
            scientific_names.append(accepted)

    sources: list[str] = []
    source_urls: list[str] = []
    if perenual:
        sources.append("Perenual")
        source_urls.append("https://perenual.com/docs/api")
    if gbif:
        sources.append("GBIF")
        source_urls.append(
            "https://api.gbif.org/v1/species/match?"
            f"name={quote(normalized_query)}&kingdom=Plantae"
        )

    warnings: list[str] = []
    if not perenual:
        warnings.append("관리 정보 API 키가 없거나 결과가 없어 분류 정보만 확인했습니다.")
    warnings.append("같은 종도 화분·흙·실내 환경에 따라 실제 수분 요구량이 달라집니다.")

    return SpeciesCareReference(
        query=original_query,
        normalized_query=normalized_query,
        common_name=_non_blank(perenual.get("common_name")) if perenual else None,
        scientific_names=scientific_names,
        watering=_non_blank(perenual.get("watering")) if perenual else None,
        sunlight=_strings(perenual.get("sunlight")) if perenual else [],
        care_level=_non_blank(perenual.get("care_level")) if perenual else None,
        indoor=(
            perenual.get("indoor")
            if perenual and isinstance(perenual.get("indoor"), bool)
            else None
        ),
        cycle=_non_blank(perenual.get("cycle")) if perenual else None,
        taxonomy=taxonomy,
        sources=sources,
        source_urls=source_urls,
        warnings=warnings,
    )


async def fetch_species_reference(
    query: str,
    settings: Settings,
    force_refresh: bool = False,
) -> SpeciesCareReference:
    original_query = " ".join(query.strip().split())
    if not original_query:
        raise SpeciesReferenceError("식물 종류를 입력해 주세요.")
    normalized_query = normalize_species_query(original_query)
    cache_key = normalized_query.casefold()
    cached = _cache.get(cache_key)
    if not force_refresh and cached and cached.expires_at > time.monotonic():
        return cached.value

    perenual: dict[str, object] | None = None
    gbif: dict[str, object] | None = None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            try:
                perenual = await _fetch_perenual(client, normalized_query, settings)
            except (httpx.HTTPError, ValueError, TypeError):
                perenual = None
            try:
                gbif = await _fetch_gbif(client, normalized_query, settings)
            except (httpx.HTTPError, ValueError, TypeError):
                gbif = None
            if perenual or gbif:
                reference = _compose_reference(
                    original_query,
                    normalized_query,
                    perenual,
                    gbif,
                )
                _cache[cache_key] = _CacheEntry(
                    time.monotonic() + CACHE_TTL_SECONDS,
                    reference,
                )
                return reference
    except httpx.RequestError:
        pass

    raise SpeciesReferenceError("무료 식물 데이터베이스에서 일치하는 종을 찾지 못했습니다.")


async def fetch_plant_species_reference(
    query: str,
    settings: Settings,
    plant_id: str | None = None,
    access_token: str = "",
    force_refresh: bool = False,
) -> SpeciesCareReference:
    normalized_query = normalize_species_query(query)
    if plant_id and access_token and not force_refresh:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                stored = await _load_plant_reference(
                    client,
                    plant_id,
                    normalized_query,
                    access_token,
                    settings,
                )
            if stored:
                return stored
        except (httpx.HTTPError, ValueError, TypeError):
            pass

    reference = await fetch_species_reference(query, settings, force_refresh=force_refresh)
    if plant_id and access_token:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await _save_plant_reference(
                    client,
                    plant_id,
                    reference,
                    access_token,
                    settings,
                )
        except (httpx.HTTPError, ValueError, TypeError):
            pass
    return reference


async def enrich_plant_reference(
    plant: PlantContext | None,
    settings: Settings,
    plant_id: str | None = None,
    access_token: str = "",
) -> PlantContext | None:
    if plant is None or not plant.species:
        return plant
    try:
        reference = await fetch_plant_species_reference(
            plant.species,
            settings,
            plant_id=plant_id,
            access_token=access_token,
        )
    except SpeciesReferenceError:
        return plant
    return plant.model_copy(update={"care_reference": reference})
