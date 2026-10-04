import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.chat import generate_reply
from app.services.plant_data import SCENARIOS

client = TestClient(app)


def test_scenario_values_and_timestamps():
    data = client.get("/api/plant/scenarios").json()
    assert len(data) == 4
    assert SCENARIOS["dry"]["sensors"]["soil_moisture"]["value"] == 15
    sensor = SCENARIOS["stale"]["sensors"]["soil_moisture"]
    assert (
        datetime.fromisoformat(SCENARIOS["stale"]["reference_time"])
        - datetime.fromisoformat(sensor["measured_at"])
    ).total_seconds() == 172800
    assert SCENARIOS["error"]["sensors"]["soil_moisture"]["value"] is None
    assert SCENARIOS["error"]["sensors"]["soil_moisture"]["measured_at"] is None


def test_selected_server_data_sent_to_provider():
    with patch("app.api.routes.chat.generate_reply", new_callable=AsyncMock) as reply:
        reply.return_value = "가상 수분 지수는 15/100이야."
        result = client.post(
            "/api/chat",
            json={"scenario": "dry", "messages": [{"role": "user", "content": "수분은?"}]},
        )
        assert result.status_code == 200
        assert reply.call_args.args[2] == SCENARIOS["dry"]
    assert (
        client.post(
            "/api/chat",
            json={"scenario": "invented", "messages": [{"role": "user", "content": "안녕"}]},
        ).status_code
        == 422
    )


def test_fixture_reaches_gemini_system_instruction():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "수분 측정 불가"}]}}]}
        )
        asyncio.run(
            generate_reply(
                [{"role": "user", "content": "수분은?"}],
                Settings(_env_file=None, gemini_api_key="test-only"),
                SCENARIOS["error"],
            )
        )
        instruction = post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"]
        assert "disconnected" in instruction
        assert "null" in instruction
        assert "가상 테스트 데이터" in instruction
        assert "초록이" in instruction


def test_korean_time_representation():
    scenario = SCENARIOS["normal"]
    reference = datetime.fromisoformat(scenario["reference_time"])
    measured = datetime.fromisoformat(scenario["sensors"]["soil_moisture"]["measured_at"])
    assert reference.utcoffset().total_seconds() == 9 * 3600
    assert (reference - measured).total_seconds() == 300
    assert scenario["sensors"]["soil_moisture"]["measured_at_kst"] == measured.strftime(
        "%Y년 %m월 %d일 %H시 %M분 KST"
    )
    assert SCENARIOS["error"]["sensors"]["soil_moisture"]["measured_at_kst"] == "측정 불가"


def test_plain_text_output_preserves_measurements():
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
        post.return_value = httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "* **수분 지수:** 15/100\n* **온도:** 23°C"}]}}
                ]
            },
        )
        reply = asyncio.run(
            generate_reply(
                [{"role": "user", "content": "상태는?"}],
                Settings(_env_file=None, gemini_api_key="test-only"),
                SCENARIOS["dry"],
            )
        )
        assert reply == "수분 지수: 15/100\n온도: 23°C"
