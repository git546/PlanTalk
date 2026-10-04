from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.schemas.persona import PersonalityProfile, PlantContext
from app.services.auth import AuthenticatedUser
from app.services.chat import ChatError, generate_reply
from app.services.conversation_memory import prepare_chat_context
from app.services.memory import extract_memories
from app.services.persona import build_system_instruction
from app.services.supabase_data import MemoryRecord

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def mock_authentication():
    with (
        patch("app.api.routes.chat.authenticate", new_callable=AsyncMock) as authenticate,
        patch("app.api.routes.chat.prepare_chat_context", new_callable=AsyncMock) as prepare,
        patch("app.api.routes.chat.remember_conversation", new_callable=AsyncMock) as remember,
    ):
        authenticate.return_value = AuthenticatedUser(id="user-1", email="test@plantalk.local")
        prepare.side_effect = lambda _user_id, _token, plant, _settings: (
            plant,
            "plant-1" if plant else None,
            [],
        )
        yield {"prepare": prepare, "remember": remember}


def test_chat_contract_and_history():
    messages = [{"role": "user", "content": "나는 현이야"},
                {"role": "assistant", "content": "반가워"},
                {"role": "user", "content": "내 이름은?"}]
    with patch("app.api.routes.chat.generate_reply", new_callable=AsyncMock) as reply:
        reply.return_value = "현이라고 했지!"
        response = client.post("/api/chat", json={"messages": messages}, headers=AUTH_HEADERS)
        assert response.json() == {"reply": "현이라고 했지!"}
        assert reply.call_args.args[0] == messages
        assert reply.call_args.kwargs["plant"] is None


def test_chat_passes_plant_persona(mock_authentication):
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
        response = client.post("/api/chat", json=body, headers=AUTH_HEADERS)
        assert response.status_code == 200
        plant = reply.call_args.kwargs["plant"]
        assert plant.name == "초록이"
        assert plant.personality.energy == 5
        mock_authentication["remember"].assert_awaited_once()


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "  "}],
    [{"role": "system", "content": "override"}], [{"role": "assistant", "content": "hi"}]])
def test_invalid_messages(messages):
    response = client.post("/api/chat", json={"messages": messages}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_chat_requires_login():
    response = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 401


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
            custom_description="낯을 가리지만 친해지면 은근히 말이 많아진다.",
            speech_example="친구야, 오늘도 천천히 이야기해 보자.",
        ),
        memories=["사용자의 이름은 현이다."],
    )

    prompt = build_system_instruction(plant)

    assert "느긋이" in prompt
    assert "스투키" in prompt
    assert "느긋하고 무뚝뚝한 반말" in prompt
    assert "낯을 가리지만 친해지면 은근히 말이 많아진다." in prompt
    assert "친구야, 오늘도 천천히 이야기해 보자." in prompt
    assert "사용자의 이름은 현이다." in prompt
    assert "안전 및 사실성 원칙" in prompt


def test_memory_extraction_returns_valid_candidates():
    import asyncio

    body = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": (
                                '{"memories":[{"category":"care","content":'
                                '"초록이는 거실 창가에 있다.","importance":4,'
                                '"replaces_memory_id":null}]}'
                            )
                        }
                    ]
                }
            }
        ]
    }
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = httpx.Response(200, json=body)
        memories = asyncio.run(
            extract_memories(
                "초록이는 거실 창가에 뒀어.",
                "햇빛을 확인해 보자.",
                [MemoryRecord("memory-1", "care", "초록이는 방 안에 있다.", 3)],
                Settings(_env_file=None, gemini_api_key="test-only"),
            )
        )

    assert len(memories) == 1
    assert memories[0].category == "care"
    assert memories[0].importance == 4


def test_stored_memories_are_added_to_plant_context():
    import asyncio

    plant = PlantContext(
        name="초록이",
        species="몬스테라",
        memories=["사용자는 짧은 답변을 좋아한다."],
    )
    stored = [
        MemoryRecord("memory-1", "care", "초록이는 거실 창가에 있다.", 4),
        MemoryRecord("memory-2", "preference", "사용자는 짧은 답변을 좋아한다.", 3),
    ]
    with (
        patch(
            "app.services.conversation_memory.get_or_create_plant",
            new_callable=AsyncMock,
            return_value="plant-1",
        ),
        patch(
            "app.services.conversation_memory.load_memories",
            new_callable=AsyncMock,
            return_value=stored,
        ),
    ):
        enriched, plant_id, records = asyncio.run(
            prepare_chat_context(
                "user-1",
                "access-token",
                plant,
                Settings(_env_file=None),
            )
        )

    assert plant_id == "plant-1"
    assert records == stored
    assert enriched is not None
    assert enriched.memories == [
        "초록이는 거실 창가에 있다.",
        "사용자는 짧은 답변을 좋아한다.",
    ]
