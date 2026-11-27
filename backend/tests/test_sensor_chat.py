import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.services.auth import AuthenticatedUser

PLANT_ID = "4f35e3bf-8142-4370-95f2-72af36c087a9"
DEVICE_ID = "device-1"


@pytest.mark.parametrize("scenario", [
    "recent", "stale", "interrupted", "watering_active", "empty", "unavailable", "unowned",
    "save_unavailable", "care_only", "both_watering_records", "inferred_unavailable",
])
def test_chat_uses_only_server_sensor_summary(scenario):
    now = datetime.now(UTC)
    age = 65 if scenario == "stale" else 5
    settings = Settings(
        _env_file=None,
        supabase_url="https://supabase.test",
        supabase_anon_key="test-anon",
        gemini_api_key="test-gemini",
    )
    measurement_queries = []
    prompts = []
    assessments = []

    def timestamp(minutes_ago):
        return (now - timedelta(minutes=minutes_ago)).isoformat()

    def handle(request):
        path = request.url.path
        params = request.url.params
        if request.url.host == "generativelanguage.googleapis.com":
            payload = json.loads(request.content)
            prompts.append(payload["systemInstruction"]["parts"][0]["text"])
            return httpx.Response(200, json={"candidates": [{"content": {
                "parts": [{"text": "최근 기록을 확인했어."}],
            }}]})
        assert request.headers["Authorization"] == "Bearer user-session"
        if path.endswith("/rpc/save_plant_water_assessment"):
            assert request.method == "POST"
            assessments.append(json.loads(request.content))
            return httpx.Response(503 if scenario == "save_unavailable" else 204)
        if path.endswith("/plants"):
            if request.method == "PATCH":
                return httpx.Response(204)
            assert params["id"] == f"eq.{PLANT_ID}"
            assert params["user_id"] == "eq.user-1"
            rows = [] if scenario == "unowned" else [{"id": PLANT_ID}]
            return httpx.Response(200, json=rows)
        assert params["plant_id"] == f"eq.{PLANT_ID}"
        if path.endswith("/memories"):
            return httpx.Response(503)
        if path.endswith("/weight_measurements"):
            if "device_id" in params:
                assert params["device_id"] == f"eq.{DEVICE_ID}"
                assert "soil_raw:raw_payload->>soil_raw" in params["select"]
                return httpx.Response(200, json=[
                    {
                        "measured_at": timestamp(age + minutes), "weight_g": 985 + minutes / 60,
                        "soil_raw": str(490 - minutes / 24), "light_raw": "720",
                        "temperature_c": 24.5, "humidity_percent": 50,
                    }
                    for minutes in range(10, 481, 10)
                ])
            measurement_queries.append(params)
            if scenario == "unavailable":
                return httpx.Response(503)
            if scenario in ("empty", "care_only", "both_watering_records", "inferred_unavailable"):
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[
                {
                    "device_id": DEVICE_ID,
                    "measured_at": timestamp(age),
                    "weight_g": "985",
                    "temperature_c": "24.5", "humidity_percent": "50",
                    "raw_payload": {"soil_raw": 490, "light_raw": 720, "ignored": "raw-only"},
                },
                {"device_id": "other-device", "measured_at": timestamp(age + 60), "weight_g": 10},
                {"device_id": DEVICE_ID, "measured_at": timestamp(age + 62), "weight_g": 1000},
            ])
        if path.endswith("/device_diagnostics"):
            assert params["device_id"] == f"eq.{DEVICE_ID}"
            if params["event_type"] == "eq.watering_suspected":
                return httpx.Response(200, json=[{
                    "occurred_at": timestamp(10 if scenario == "watering_active" else 660),
                    "details": {"increase_g": 25},
                }])
            rows = [{"occurred_at": timestamp(2)}] if scenario == "interrupted" else []
            return httpx.Response(200, json=rows)
        if path.endswith("/care_events"):
            assert params["source"] == "in.(manual,device)"
            rows = [
                {
                    "occurred_at": timestamp(120), "event_type": "watering",
                    "source": "manual", "volume_ml": 25,
                },
                {
                    "occurred_at": timestamp(90), "event_type": "watering",
                    "source": "simulator", "volume_ml": 999,
                },
            ] if scenario in ("care_only", "both_watering_records", "inferred_unavailable") else []
            return httpx.Response(200, json=rows)
        if path.endswith("/plant_watering_records"):
            assert params["record_kind"] == "eq.inferred"
            if scenario == "inferred_unavailable":
                return httpx.Response(503)
            rows = [{
                "occurred_at": timestamp(118),
                "estimated_from_at": timestamp(123),
                "observed_weight_increase_g": "29.686",
            }] if scenario == "both_watering_records" else []
            return httpx.Response(200, json=rows)
        if path.endswith("/plant_water_calibrations"):
            assert params["select"] == "id,calibrated_at"
            return httpx.Response(200, json=[])
        pytest.fail(f"Unexpected request: {path}")

    real_client = httpx.AsyncClient

    def mock_client(**kwargs):
        return real_client(transport=httpx.MockTransport(handle), **kwargs)

    with (
        patch("httpx.AsyncClient", side_effect=mock_client),
        patch("app.api.routes.chat.get_settings", return_value=settings),
        patch("app.api.routes.chat.authenticate", AsyncMock(return_value=AuthenticatedUser(
            id="user-1", email="test@plantalk.local",
        ))),
        patch("app.api.routes.chat.remember_conversation", new_callable=AsyncMock),
    ):
        response = TestClient(app).post(
            "/api/chat",
            headers={"Authorization": "Bearer user-session"},
            json={
                "messages": [{"role": "user", "content": "지금 물 줘야 해?"}],
                "plant": {"id": PLANT_ID, "name": "초록이"},
                "time_zone": "Asia/Seoul",
            },
        )

    assert response.status_code == 200
    [prompt] = prompts
    assert "raw-only" not in prompt
    assert '"time_zone": "Asia/Seoul"' in prompt
    if scenario == "unowned":
        assert not measurement_queries
        assert not assessments
        assert '"sensor_observations"' not in prompt
        assert '"recent_care_records":' not in prompt
        assert '"watering_history":' not in prompt
        return
    [params] = measurement_queries
    assert params["source"] == "eq.device"
    assert params["is_stable"] == "eq.true"
    assert params["and"].startswith("(measured_at.gte.")
    expected_status = {
        "watering_active": "recent", "empty": "no_reading_in_last_24_hours",
        "save_unavailable": "recent",
        "care_only": "no_reading_in_last_24_hours",
        "both_watering_records": "no_reading_in_last_24_hours",
        "inferred_unavailable": "no_reading_in_last_24_hours",
    }.get(scenario, scenario)
    assert f'"status": "{expected_status}"' in prompt
    if expected_status in ("no_reading_in_last_24_hours", "unavailable"):
        assert not assessments
    else:
        [saved] = assessments
        assert saved["p_plant_id"] == PLANT_ID
        assert saved["p_device_id"] == DEVICE_ID
        assert saved["p_observation_status"] == expected_status
        assert saved["p_measured_at"] == saved["p_summary"]["measured_at"]
        assert saved["p_evaluated_at"] >= saved["p_measured_at"]

    if scenario in ("care_only", "both_watering_records", "inferred_unavailable"):
        data = json.loads(prompt.split("```json\n", 1)[1].split("\n```", 1)[0])
        history = data["watering_history"]
        [direct] = history["direct"]["events"]
        assert direct["volume_ml"] == 25.0
        assert direct["occurred_at"]["minutes_ago"] == 120.0
        assert data["recent_care_records"]["events"] == []
        if scenario == "both_watering_records":
            [inferred] = history["inferred"]["events"]
            assert inferred["observed_weight_increase_g"] == 29.686
            assert inferred["estimated_from_at"]["minutes_ago"] == 123.0
            assert inferred["occurred_at"]["minutes_ago"] == 118.0
            assert "volume_ml" not in inferred
        if scenario == "inferred_unavailable":
            assert history["inferred"] == {"status": "unavailable", "events": []}

    if scenario in ("recent", "save_unavailable"):
        assert '"weight_g": 985.0' in prompt
        assert '"soil_raw": 490.0' in prompt
        assert '"observed_weight_increase_g": 25.0' in prompt
        assert '"status": "drying"' in prompt
        assert '"baseline_weight_g": 992.83' in prompt
        assert '"estimated_replenishment_ml":' in prompt
        assert '"loss_evidence": "weight_and_soil"' in prompt
        assert '"unit": "raw_adc"' in prompt
        assert '"air_vpd_kpa":' in prompt
        assert saved["p_summary"]["water_assessment"]["loss_evidence"] == "weight_and_soil"
    else:
        assert '"estimated_replenishment_ml":' not in prompt
        if scenario == "watering_active":
            assert '"within_30_minutes": true' in prompt
            assert '"status": "settling_after_watering"' in prompt
        else:
            assert '"drydown":' not in prompt
