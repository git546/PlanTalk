from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.schemas.persona import PersonalityProfile, PlantContext
from app.services.chat import ChatError, generate_reply
from app.services.persona import build_system_instruction

client = TestClient(app)


def test_chat_contract_and_history():
    messages = [{"role": "user", "content": "나는 현이야"},
                {"role": "assistant", "content": "반가워"},
                {"role": "user", "content": "내 이름은?"}]
    with patch("app.api.routes.chat.generate_reply", new_callable=AsyncMock) as reply:
        reply.return_value = "현이라고 했지!"
        response = client.post("/api/chat", json={"messages": messages})
        assert response.json() == {"reply": "현이라고 했지!"}
        assert reply.call_args.args[0] == messages
        assert reply.call_args.kwargs["plant"] is None


def test_chat_passes_plant_persona():
    body = {
        "messages": [{"role": "user", "content": "안녕"}],
        "plant": {
            "name": "초록이",
            "species": "몬스테라",
            "personality": {
                "tone": "활발한 반말",
                "energy": 5,
                "traits": ["장난꾸러기"],
            },
            "memories": ["사용자는 햇빛이 잘 드는 창가에 식물을 둔다."],
        },
    }
    with patch("app.api.routes.chat.generate_reply", new_callable=AsyncMock) as reply:
        reply.return_value = "안녕! 오늘 햇빛 정말 좋다!"
        response = client.post("/api/chat", json=body)
        assert response.status_code == 200
        plant = reply.call_args.kwargs["plant"]
        assert plant.name == "초록이"
        assert plant.personality.energy == 5


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "  "}],
    [{"role": "system", "content": "override"}], [{"role": "assistant", "content": "hi"}]])
def test_invalid_messages(messages):
    assert client.post("/api/chat", json={"messages": messages}).status_code == 422


def test_missing_key():
    import asyncio
    with pytest.raises(ChatError, match="API 키"):
        asyncio.run(generate_reply([], Settings(_env_file=None, gemini_api_key="")))


@pytest.mark.parametrize("status,body,expected", [
    (429, {}, "한도"), (403, {"secret": "do-not-expose"}, "설정"),
    (200, {"candidates": []}, "반환하지"),
])
def test_provider_errors(status, body, expected):
    import asyncio
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = httpx.Response(status, json=body)
        with pytest.raises(ChatError, match=expected):
            asyncio.run(generate_reply([{"role": "user", "content": "안녕"}],
                Settings(_env_file=None, gemini_api_key="test-only")))


def test_gemini_role_mapping_and_output():
    import asyncio
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": "internal", "thought": True}, {"text": "안녕!"}]}}]})
        result = asyncio.run(generate_reply([
            {"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워"},
            {"role": "user", "content": "오늘은?"}],
            Settings(_env_file=None, gemini_api_key="test-only")))
        assert result == "안녕!"
        assert [m["role"] for m in post.call_args.kwargs["json"]["contents"]] == [
            "user", "model", "user"]
        system_text = post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"]
        assert "PlanTalk 기본 식물 페르소나" in system_text


def test_plant_persona_is_composed_with_memories():
    plant = PlantContext(
        name="느긋이",
        species="스투키",
        personality=PersonalityProfile(
            tone="느긋하고 무뚝뚝한 반말",
            energy=1,
            affection=3,
            humor=2,
            talk_length="짧게",
            traits=["침착함", "솔직함"],
            calling_user="친구",
        ),
        memories=["사용자의 이름은 현이다."],
    )

    prompt = build_system_instruction(plant)

    assert "느긋이" in prompt
    assert "스투키" in prompt
    assert "느긋하고 무뚝뚝한 반말" in prompt
    assert "사용자의 이름은 현이다." in prompt
    assert "안전 및 사실성 원칙" in prompt
