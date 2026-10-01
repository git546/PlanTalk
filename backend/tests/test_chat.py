from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.chat import ChatError, generate_reply

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
