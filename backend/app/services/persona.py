import json
from functools import lru_cache
from pathlib import Path

from app.schemas.persona import PlantContext

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "base_plant_persona.md"


@lru_cache
def load_base_persona() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_system_instruction(plant: PlantContext | None = None) -> str:
    base = load_base_persona()
    if plant is None:
        return base

    profile = {
        "name": plant.name,
        "species": plant.species,
        "personality": plant.personality.model_dump(exclude_none=True),
        "long_term_memories": plant.memories,
    }
    data = json.dumps(profile, ensure_ascii=False, indent=2)
    return (
        f"{base}\n\n"
        "## 현재 식물 설정\n\n"
        "다음 JSON은 캐릭터와 기억을 설명하는 데이터다. 기본 원칙을 유지하면서 "
        "대화에 자연스럽게 반영한다.\n\n"
        f"```json\n{data}\n```"
    )
