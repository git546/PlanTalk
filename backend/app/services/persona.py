import json
from functools import lru_cache
from pathlib import Path

from app.schemas.persona import PlantContext
from app.services.chat_time import ChatClock

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "base_plant_persona.md"


@lru_cache
def load_base_persona() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_system_instruction(
    plant: PlantContext | None = None,
    *,
    sensor_context: dict[str, object] | None = None,
    clock: ChatClock | None = None,
) -> str:
    base = load_base_persona()
    if plant is None and clock is None and sensor_context is None:
        return base

    profile: dict[str, object] = {}
    if clock is not None:
        profile["time_context"] = clock.current()
    if plant is not None:
        profile.update({
            "name": plant.name,
            "species": plant.species,
            "personality": plant.personality.model_dump(exclude_none=True),
            "long_term_memories": plant.memories,
            "external_care_reference": (
                plant.care_reference.model_dump(exclude_none=True) if plant.care_reference else None
            ),
        })
    if sensor_context is not None:
        observations = sensor_context.copy()
        for key in ("recent_care_records", "watering_history"):
            records = observations.pop(key, None)
            if records is not None:
                profile[key] = clock.localize_records(records) if clock else records
        profile["sensor_observations"] = (
            clock.localize_records(observations) if clock else observations
        )
    data = json.dumps(profile, ensure_ascii=False, indent=2)
    return (
        f"{base}\n\n"
        "## 현재 대화 정보\n\n"
        "다음 JSON은 현재 시각, 캐릭터, 기억, 관리 기록과 센서 관측을 담는다. 기본 원칙을 "
        "유지하면서 대화에 자연스럽게 반영한다. 외부 관리 정보는 일반적인 종별 참고값일 "
        "뿐이므로 센서·화분 무게·사용자의 실제 관찰과 충돌하면 실제 측정값을 우선한다.\n\n"
        f"```json\n{data}\n```"
    )
