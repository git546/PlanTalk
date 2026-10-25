from dataclasses import dataclass
from typing import Literal

WaterStatus = Literal["hydrated", "monitor", "water_soon", "water_now"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class WaterBalanceInput:
    """Hardware-independent values required by the deterministic calculator."""

    period_days: float
    start_pot_weight_g: float
    end_pot_weight_g: float
    water_added_ml: float
    drainage_ml: float
    target_wet_weight_g: float
    watering_trigger_weight_g: float
    max_single_watering_ml: float | None = None


@dataclass(frozen=True)
class WaterBalanceCalculation:
    observation_period_days: float
    storage_change_ml: float
    net_water_added_ml: float
    estimated_water_loss_ml: float
    average_daily_loss_ml: float
    drainage_ratio_percent: float | None
    refill_to_target_ml: float
    recommended_water_now_ml: float
    estimated_days_until_watering: float | None
    status: WaterStatus
    confidence: Confidence
    warnings: tuple[str, ...]


def _rounded(value: float) -> float:
    return round(value, 2)


def calculate(input_data: WaterBalanceInput) -> WaterBalanceCalculation:
    """Calculate water balance without knowing how measurements were collected."""

    warnings: list[str] = []
    storage_change = input_data.end_pot_weight_g - input_data.start_pot_weight_g
    net_water_added = input_data.water_added_ml - input_data.drainage_ml
    raw_water_loss = net_water_added - storage_change

    if input_data.drainage_ml > input_data.water_added_ml:
        warnings.append(
            "배수량이 급수량보다 많습니다. 이전에 저장된 물이 배출됐거나 측정값을 확인해야 합니다."
        )
    if raw_water_loss < 0:
        warnings.append(
            "계산된 수분 손실이 음수입니다. 측정 시점, 화분 무게 또는 급수·배수량을 확인해 주세요."
        )
    if input_data.period_days < 2:
        warnings.append("측정 기간이 짧아 하루 평균 소비량의 변동이 클 수 있습니다.")
    elif input_data.period_days > 14:
        warnings.append("측정 기간이 길어 성장이나 환경 변화가 평균값에 섞였을 수 있습니다.")
    if input_data.end_pot_weight_g > input_data.target_wet_weight_g:
        warnings.append(
            "현재 무게가 충분히 젖은 목표 무게보다 큽니다. 배수 완료 여부를 확인해 주세요."
        )

    estimated_water_loss = max(raw_water_loss, 0)
    average_daily_loss = estimated_water_loss / input_data.period_days
    drainage_ratio = (
        input_data.drainage_ml / input_data.water_added_ml * 100
        if input_data.water_added_ml > 0
        else None
    )
    refill_to_target = max(input_data.target_wet_weight_g - input_data.end_pot_weight_g, 0)

    if input_data.end_pot_weight_g <= input_data.watering_trigger_weight_g:
        status: WaterStatus = "water_now"
        recommended_now = refill_to_target
        days_until_watering = 0.0
    elif input_data.end_pot_weight_g >= input_data.target_wet_weight_g:
        status = "hydrated"
        recommended_now = 0.0
        days_until_watering = (
            (input_data.end_pot_weight_g - input_data.watering_trigger_weight_g)
            / average_daily_loss
            if average_daily_loss > 0
            else None
        )
    else:
        recommended_now = 0.0
        days_until_watering = (
            (input_data.end_pot_weight_g - input_data.watering_trigger_weight_g)
            / average_daily_loss
            if average_daily_loss > 0
            else None
        )
        status = (
            "water_soon"
            if days_until_watering is not None and days_until_watering <= 2
            else "monitor"
        )

    if input_data.max_single_watering_ml is not None:
        recommended_now = min(recommended_now, input_data.max_single_watering_ml)

    if warnings:
        confidence: Confidence = "low" if raw_water_loss < 0 else "medium"
    elif 2 <= input_data.period_days <= 14:
        confidence = "high"
    else:
        confidence = "medium"

    return WaterBalanceCalculation(
        observation_period_days=_rounded(input_data.period_days),
        storage_change_ml=_rounded(storage_change),
        net_water_added_ml=_rounded(net_water_added),
        estimated_water_loss_ml=_rounded(estimated_water_loss),
        average_daily_loss_ml=_rounded(average_daily_loss),
        drainage_ratio_percent=_rounded(drainage_ratio) if drainage_ratio is not None else None,
        refill_to_target_ml=_rounded(refill_to_target),
        recommended_water_now_ml=_rounded(recommended_now),
        estimated_days_until_watering=(
            _rounded(days_until_watering) if days_until_watering is not None else None
        ),
        status=status,
        confidence=confidence,
        warnings=tuple(warnings),
    )
