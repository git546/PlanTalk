from dataclasses import dataclass

import httpx

from app.core.config import Settings
from app.schemas.persona import PlantContext


class DataStoreError(Exception):
    pass


@dataclass(frozen=True)
class MemoryRecord:
    id: str
    category: str
    content: str
    importance: int


def _base_url(settings: Settings) -> str:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise DataStoreError("Supabase 데이터 저장 설정이 완료되지 않았습니다.")
    return f"{settings.supabase_url.rstrip('/')}/rest/v1"


def _headers(settings: Settings, access_token: str, prefer: str | None = None) -> dict[str, str]:
    if not settings.supabase_anon_key:
        raise DataStoreError("Supabase 데이터 저장 설정이 완료되지 않았습니다.")
    headers = {
        "apikey": settings.supabase_anon_key.get_secret_value(),
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


async def get_or_create_plant(
    user_id: str,
    access_token: str,
    plant: PlantContext,
    settings: Settings,
) -> str:
    base_url = _base_url(settings)
    headers = _headers(settings, access_token)
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(
            f"{base_url}/plants",
            headers=headers,
            params={
                "select": "id,name",
                "user_id": f"eq.{user_id}",
                "order": "created_at.asc",
                "limit": "1",
            },
        )
        if response.is_error:
            raise DataStoreError("식물 정보를 불러오지 못했습니다.")
        rows = response.json()
        values = {
            "name": plant.name,
            "personality_overrides": plant.personality.model_dump(exclude_none=True),
            "care_overrides": {"species_label": plant.species} if plant.species else {},
        }
        if rows:
            plant_id = rows[0]["id"]
            update = await client.patch(
                f"{base_url}/plants",
                headers=_headers(settings, access_token, "return=minimal"),
                params={"id": f"eq.{plant_id}"},
                json=values,
            )
            if update.is_error:
                raise DataStoreError("식물 설정을 저장하지 못했습니다.")
            return plant_id

        create = await client.post(
            f"{base_url}/plants",
            headers=_headers(settings, access_token, "return=representation"),
            json={"user_id": user_id, **values},
        )
        if create.is_error:
            raise DataStoreError("식물 정보를 만들지 못했습니다.")
        try:
            return create.json()[0]["id"]
        except (IndexError, KeyError, TypeError, ValueError):
            raise DataStoreError("생성된 식물 정보를 확인하지 못했습니다.") from None


async def load_memories(
    plant_id: str,
    access_token: str,
    settings: Settings,
    limit: int = 20,
) -> list[MemoryRecord]:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(
            f"{_base_url(settings)}/memories",
            headers=_headers(settings, access_token),
            params={
                "select": "id,category,content,importance",
                "plant_id": f"eq.{plant_id}",
                "is_active": "eq.true",
                "order": "importance.desc,updated_at.desc",
                "limit": str(limit),
            },
        )
    if response.is_error:
        raise DataStoreError("장기 기억을 불러오지 못했습니다.")
    try:
        return [MemoryRecord(**row) for row in response.json()]
    except (TypeError, ValueError):
        raise DataStoreError("장기 기억 형식이 올바르지 않습니다.") from None


async def save_message_pair(
    plant_id: str,
    user_message: str,
    assistant_reply: str,
    access_token: str,
    settings: Settings,
) -> int | None:
    rows = [
        {"plant_id": plant_id, "role": "user", "content": user_message[:4000]},
        {"plant_id": plant_id, "role": "assistant", "content": assistant_reply[:4000]},
    ]
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            f"{_base_url(settings)}/messages",
            headers=_headers(settings, access_token, "return=representation"),
            json=rows,
        )
    if response.is_error:
        raise DataStoreError("대화 기록을 저장하지 못했습니다.")
    try:
        return int(response.json()[0]["id"])
    except (IndexError, KeyError, TypeError, ValueError):
        return None


async def save_memory_candidates(
    plant_id: str,
    candidates: list[dict[str, object]],
    existing: list[MemoryRecord],
    source_message_id: int | None,
    access_token: str,
    settings: Settings,
) -> int:
    if not candidates:
        return 0
    existing_by_id = {memory.id: memory for memory in existing}
    existing_contents = {memory.content.strip().casefold() for memory in existing}
    rows: list[dict[str, object]] = []
    replace_ids: set[str] = set()
    for candidate in candidates:
        content = str(candidate["content"]).strip()
        if content.casefold() in existing_contents:
            continue
        replace_id = candidate.get("replaces_memory_id")
        if isinstance(replace_id, str) and replace_id in existing_by_id:
            replace_ids.add(replace_id)
        rows.append(
            {
                "plant_id": plant_id,
                "category": candidate["category"],
                "content": content,
                "importance": candidate["importance"],
                "source_message_id": source_message_id,
            }
        )
        existing_contents.add(content.casefold())

    async with httpx.AsyncClient(timeout=12) as client:
        for memory_id in replace_ids:
            response = await client.patch(
                f"{_base_url(settings)}/memories",
                headers=_headers(settings, access_token, "return=minimal"),
                params={"id": f"eq.{memory_id}"},
                json={"is_active": False},
            )
            if response.is_error:
                raise DataStoreError("기존 장기 기억을 갱신하지 못했습니다.")
        if rows:
            response = await client.post(
                f"{_base_url(settings)}/memories",
                headers=_headers(settings, access_token, "return=minimal"),
                json=rows,
            )
            if response.is_error:
                raise DataStoreError("장기 기억을 저장하지 못했습니다.")
    return len(rows)
