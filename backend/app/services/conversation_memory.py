import logging

import httpx

from app.core.config import Settings
from app.schemas.persona import PlantContext
from app.services.memory import extract_memories, memory_candidates_as_dicts
from app.services.supabase_data import (
    DataStoreError,
    MemoryRecord,
    get_or_create_plant,
    load_memories,
    save_memory_candidates,
    save_message_pair,
)

logger = logging.getLogger(__name__)


async def prepare_chat_context(
    user_id: str,
    access_token: str,
    plant: PlantContext | None,
    settings: Settings,
) -> tuple[PlantContext | None, str | None, list[MemoryRecord]]:
    if plant is None:
        return None, None, []
    try:
        plant_id = await get_or_create_plant(user_id, access_token, plant, settings)
        stored_memories = await load_memories(plant_id, access_token, settings)
    except (DataStoreError, httpx.RequestError, OSError) as exc:
        logger.warning("Could not prepare conversation memory: %s", exc)
        return plant, None, []

    contents: list[str] = []
    seen: set[str] = set()
    for content in [*(memory.content for memory in stored_memories), *plant.memories]:
        normalized = content.strip().casefold()
        if normalized and normalized not in seen:
            contents.append(content.strip())
            seen.add(normalized)
        if len(contents) >= 20:
            break
    return plant.model_copy(update={"memories": contents}), plant_id, stored_memories


async def remember_conversation(
    plant_id: str,
    user_message: str,
    assistant_reply: str,
    existing_memories: list[MemoryRecord],
    access_token: str,
    settings: Settings,
) -> None:
    try:
        source_message_id = await save_message_pair(
            plant_id,
            user_message,
            assistant_reply,
            access_token,
            settings,
        )
        candidates = await extract_memories(
            user_message,
            assistant_reply,
            existing_memories,
            settings,
        )
        await save_memory_candidates(
            plant_id,
            memory_candidates_as_dicts(candidates),
            existing_memories,
            source_message_id,
            access_token,
            settings,
        )
    except (DataStoreError, httpx.RequestError, OSError) as exc:
        logger.warning("Could not persist conversation memory: %s", exc)
