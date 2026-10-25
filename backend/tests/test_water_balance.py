from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.water_balance import (
    WaterBalanceEvaluationRequest,
    WaterBalanceRequest,
)
from app.services.auth import AuthenticatedUser
from app.services.water_balance import (
    calculate_measurement_window,
    calculate_water_balance,
)

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def mock_authentication():
    with patch("app.api.routes.chat.authenticate", new_callable=AsyncMock) as authenticate:
        authenticate.return_value = AuthenticatedUser(id="user-1", email="test@plantalk.local")
        yield


def example_request(**overrides: float) -> WaterBalanceRequest:
    values = {
        "period_days": 3,
        "start_pot_weight_g": 3800,
        "end_pot_weight_g": 3550,
        "water_added_ml": 500,
        "drainage_ml": 100,
        "target_wet_weight_g": 3800,
        "watering_trigger_weight_g": 3300,
        "max_single_watering_ml": 600,
    }
    values.update(overrides)
    return WaterBalanceRequest(**values)


def measurement_request(
    *,
    source: str = "simulator",
    start_device_id: str | None = "simulator-01",
    end_device_id: str | None = "simulator-01",
    start_stable: bool = True,
    end_stable: bool = True,
) -> WaterBalanceEvaluationRequest:
    started_at = datetime(2026, 10, 1, 9, tzinfo=UTC)
    return WaterBalanceEvaluationRequest.model_validate(
        {
            "plant_id": "plant-1",
            "calibration": {
                "setup_weight_g": 2800,
                "target_wet_weight_g": 3800,
                "watering_trigger_weight_g": 3300,
                "max_single_watering_ml": 600,
                "calibrated_at": "2026-09-30T09:00:00Z",
                "version": 1,
            },
            "start_measurement": {
                "measured_at": started_at,
                "weight_g": 3800,
                "source": source,
                "device_id": start_device_id,
                "sequence_no": 10,
                "is_stable": start_stable,
                "raw_sensor_value": 842000,
                "sample_count": 20,
            },
            "end_measurement": {
                "measured_at": started_at + timedelta(days=3),
                "weight_g": 3550,
                "source": source,
                "device_id": end_device_id,
                "sequence_no": 11,
                "is_stable": end_stable,
                "raw_sensor_value": 788000,
                "sample_count": 20,
            },
            "water_added_ml": 500,
            "drainage_ml": 100,
            "environment": {
                "temperature_c": 24.5,
                "humidity_percent": 55,
                "light_lux": 12000,
            },
        }
    )


def test_calculates_water_balance_and_forecast() -> None:
    result = calculate_water_balance(example_request())

    assert result.storage_change_ml == -250
    assert result.net_water_added_ml == 400
    assert result.estimated_water_loss_ml == 650
    assert result.average_daily_loss_ml == 216.67
    assert result.drainage_ratio_percent == 20
    assert result.refill_to_target_ml == 250
    assert result.recommended_water_now_ml == 0
    assert result.estimated_days_until_watering == 1.15
    assert result.status == "water_soon"
    assert result.confidence == "high"
    assert result.observation_period_days == 3
    assert result.trace.input_mode == "legacy"


def test_recommends_water_only_after_trigger() -> None:
    result = calculate_water_balance(
        example_request(end_pot_weight_g=3200, watering_trigger_weight_g=3250)
    )

    assert result.status == "water_now"
    assert result.refill_to_target_ml == 600
    assert result.recommended_water_now_ml == 600
    assert result.estimated_days_until_watering == 0


def test_caps_single_watering_amount() -> None:
    result = calculate_water_balance(
        example_request(
            end_pot_weight_g=3000,
            watering_trigger_weight_g=3250,
            max_single_watering_ml=450,
        )
    )

    assert result.refill_to_target_ml == 800
    assert result.recommended_water_now_ml == 450


def test_inconsistent_measurements_return_warning() -> None:
    result = calculate_water_balance(
        example_request(
            start_pot_weight_g=3500,
            end_pot_weight_g=3800,
            water_added_ml=100,
            drainage_ml=0,
        )
    )

    assert result.estimated_water_loss_ml == 0
    assert result.average_daily_loss_ml == 0
    assert result.confidence == "low"
    assert any("음수" in warning for warning in result.warnings)


def test_water_balance_api_requires_login() -> None:
    response = client.post("/api/water-balance", json=example_request().model_dump())

    assert response.status_code == 401


def test_water_balance_api_returns_result() -> None:
    response = client.post(
        "/api/water-balance",
        json=example_request().model_dump(),
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "water_soon"
    assert response.json()["trace"]["calculation_version"] == "water-balance-rules-v1"


def test_rejects_invalid_weight_thresholds() -> None:
    body = example_request().model_dump()
    body["watering_trigger_weight_g"] = body["target_wet_weight_g"]

    response = client.post("/api/water-balance", json=body, headers=AUTH_HEADERS)

    assert response.status_code == 422


def test_measurement_window_matches_manual_calculation() -> None:
    result = calculate_measurement_window(measurement_request())

    assert result.estimated_water_loss_ml == 650
    assert result.average_daily_loss_ml == 216.67
    assert result.status == "water_soon"
    assert result.confidence == "high"
    assert result.trace.input_mode == "measurement_window"
    assert result.trace.measurement_sources == ["simulator"]
    assert result.trace.device_ids == ["simulator-01"]


def test_unstable_device_reading_lowers_confidence() -> None:
    result = calculate_measurement_window(
        measurement_request(source="device", end_stable=False)
    )

    assert result.confidence == "medium"
    assert any("안정화되지 않은" in warning for warning in result.warnings)


def test_different_devices_lower_confidence() -> None:
    result = calculate_measurement_window(
        measurement_request(
            source="device",
            start_device_id="scale-a",
            end_device_id="scale-b",
        )
    )

    assert result.confidence == "medium"
    assert result.trace.device_ids == ["scale-a", "scale-b"]
    assert any("측정 기기가 다릅니다" in warning for warning in result.warnings)


def test_device_measurement_requires_device_id() -> None:
    body = measurement_request().model_dump(mode="json")
    body["start_measurement"]["source"] = "device"
    body["start_measurement"]["device_id"] = None

    response = client.post(
        "/api/water-balance/evaluate",
        json=body,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422


def test_measurement_api_requires_login() -> None:
    response = client.post(
        "/api/water-balance/evaluate",
        json=measurement_request().model_dump(mode="json"),
    )

    assert response.status_code == 401


def test_measurement_api_returns_trace() -> None:
    response = client.post(
        "/api/water-balance/evaluate",
        json=measurement_request().model_dump(mode="json"),
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["observation_period_days"] == 3
    assert body["trace"]["measurement_sources"] == ["simulator"]
    assert body["trace"]["device_ids"] == ["simulator-01"]


def test_rejects_measurement_window_longer_than_ninety_days() -> None:
    body = measurement_request().model_dump(mode="json")
    body["end_measurement"]["measured_at"] = "2027-01-01T09:00:00Z"

    response = client.post(
        "/api/water-balance/evaluate",
        json=body,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
