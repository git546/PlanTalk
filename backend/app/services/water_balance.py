from dataclasses import replace

from app.domain.water_balance import (
    Confidence,
    WaterBalanceCalculation,
    WaterBalanceInput,
    calculate,
)
from app.schemas.water_balance import (
    WaterBalanceEvaluationRequest,
    WaterBalanceRequest,
    WaterBalanceResponse,
    WaterBalanceTrace,
)


def _lower_confidence(confidence: Confidence) -> Confidence:
    if confidence == "high":
        return "medium"
    return "low"


def _build_response(
    result: WaterBalanceCalculation,
    trace: WaterBalanceTrace,
) -> WaterBalanceResponse:
    return WaterBalanceResponse(
        observation_period_days=result.observation_period_days,
        storage_change_ml=result.storage_change_ml,
        net_water_added_ml=result.net_water_added_ml,
        estimated_water_loss_ml=result.estimated_water_loss_ml,
        average_daily_loss_ml=result.average_daily_loss_ml,
        drainage_ratio_percent=result.drainage_ratio_percent,
        refill_to_target_ml=result.refill_to_target_ml,
        recommended_water_now_ml=result.recommended_water_now_ml,
        estimated_days_until_watering=result.estimated_days_until_watering,
        status=result.status,
        confidence=result.confidence,
        warnings=list(result.warnings),
        trace=trace,
    )


def calculate_water_balance(data: WaterBalanceRequest) -> WaterBalanceResponse:
    """Compatibility adapter for the existing manual calculator request."""

    result = calculate(
        WaterBalanceInput(
            period_days=data.period_days,
            start_pot_weight_g=data.start_pot_weight_g,
            end_pot_weight_g=data.end_pot_weight_g,
            water_added_ml=data.water_added_ml,
            drainage_ml=data.drainage_ml,
            target_wet_weight_g=data.target_wet_weight_g,
            watering_trigger_weight_g=data.watering_trigger_weight_g,
            max_single_watering_ml=data.max_single_watering_ml,
        )
    )
    return _build_response(
        result,
        WaterBalanceTrace(
            input_mode="legacy",
            measurement_sources=["manual"],
        ),
    )


def calculate_measurement_window(
    data: WaterBalanceEvaluationRequest,
) -> WaterBalanceResponse:
    """Evaluate timestamped readings from manual input, a simulator, or a device."""

    elapsed_seconds = (
        data.end_measurement.measured_at - data.start_measurement.measured_at
    ).total_seconds()
    period_days = elapsed_seconds / 86_400
    result = calculate(
        WaterBalanceInput(
            period_days=period_days,
            start_pot_weight_g=data.start_measurement.weight_g,
            end_pot_weight_g=data.end_measurement.weight_g,
            water_added_ml=data.water_added_ml,
            drainage_ml=data.drainage_ml,
            target_wet_weight_g=data.calibration.target_wet_weight_g,
            watering_trigger_weight_g=data.calibration.watering_trigger_weight_g,
            max_single_watering_ml=data.calibration.max_single_watering_ml,
        )
    )

    extra_warnings: list[str] = []
    measurements = (data.start_measurement, data.end_measurement)
    if any(not measurement.is_stable for measurement in measurements):
        extra_warnings.append(
            "안정화되지 않은 무게 측정값이 포함되어 있어 결과 신뢰도를 낮췄습니다."
        )

    device_ids = sorted(
        {
            measurement.device_id
            for measurement in measurements
            if measurement.device_id is not None
        }
    )
    if len(device_ids) > 1:
        extra_warnings.append(
            "시작과 종료 측정 기기가 다릅니다. 기기별 영점 차이를 확인해 주세요."
        )

    if extra_warnings:
        result = replace(
            result,
            confidence=_lower_confidence(result.confidence),
            warnings=(*result.warnings, *extra_warnings),
        )

    sources = list(dict.fromkeys(measurement.source for measurement in measurements))
    return _build_response(
        result,
        WaterBalanceTrace(
            input_mode="measurement_window",
            measurement_sources=sources,
            started_at=data.start_measurement.measured_at,
            ended_at=data.end_measurement.measured_at,
            device_ids=device_ids,
        ),
    )
