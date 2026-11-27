from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

WaterStatus = Literal["hydrated", "monitor", "water_soon", "water_now"]
Confidence = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class LabInput:
    """One observation window collected manually or from a prototype device."""

    period_days: float
    start_pot_weight_g: float
    end_pot_weight_g: float
    water_added_ml: float
    drainage_ml: float
    target_wet_weight_g: float
    watering_trigger_weight_g: float
    max_single_watering_ml: float | None = None

    def validate(self) -> None:
        positive_values = {
            "측정 기간": self.period_days,
            "시작 화분 무게": self.start_pot_weight_g,
            "종료 화분 무게": self.end_pot_weight_g,
            "충분히 젖은 목표 무게": self.target_wet_weight_g,
            "물주기 기준 무게": self.watering_trigger_weight_g,
        }
        for label, value in positive_values.items():
            if value <= 0:
                raise ValueError(f"{label}은(는) 0보다 커야 합니다.")
        if self.water_added_ml < 0 or self.drainage_ml < 0:
            raise ValueError("급수량과 배수량은 0 이상이어야 합니다.")
        if self.watering_trigger_weight_g >= self.target_wet_weight_g:
            raise ValueError("물주기 기준 무게는 젖은 목표 무게보다 작아야 합니다.")
        if self.max_single_watering_ml is not None and self.max_single_watering_ml <= 0:
            raise ValueError("1회 최대 급수량은 비워 두거나 0보다 커야 합니다.")


@dataclass(frozen=True)
class TuningProfile:
    """Experimental coefficients. Defaults reproduce the production v1 rules."""

    name: str = "기본값"
    water_density_g_per_ml: float = 1.0
    loss_scale: float = 1.0
    loss_bias_ml: float = 0.0
    recommendation_scale: float = 1.0
    trigger_margin_g: float = 0.0
    version: int = 1

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("프로필 이름을 입력해 주세요.")
        if self.water_density_g_per_ml <= 0:
            raise ValueError("물 밀도는 0보다 커야 합니다.")
        if self.loss_scale < 0:
            raise ValueError("손실 보정 배수는 0 이상이어야 합니다.")
        if self.recommendation_scale < 0:
            raise ValueError("권장 급수 보정 배수는 0 이상이어야 합니다.")
        if self.version < 1:
            raise ValueError("프로필 버전은 1 이상이어야 합니다.")


@dataclass(frozen=True)
class LabResult:
    observation_period_days: float
    storage_change_ml: float
    net_water_added_ml: float
    raw_water_loss_ml: float
    estimated_water_loss_ml: float
    average_daily_loss_ml: float
    drainage_ratio_percent: float | None
    refill_to_target_ml: float
    recommended_water_now_ml: float
    estimated_days_until_watering: float | None
    effective_trigger_weight_g: float
    status: WaterStatus
    confidence: Confidence
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _rounded(value: float) -> float:
    return round(value, 2)


def calculate(input_data: LabInput, profile: TuningProfile | None = None) -> LabResult:
    """Run the experimental calculator without FastAPI, Supabase, or mobile UI."""

    profile = profile or TuningProfile()
    input_data.validate()
    profile.validate()

    warnings: list[str] = []
    storage_change_ml = (
        input_data.end_pot_weight_g - input_data.start_pot_weight_g
    ) / profile.water_density_g_per_ml
    net_water_added_ml = input_data.water_added_ml - input_data.drainage_ml
    raw_water_loss_ml = net_water_added_ml - storage_change_ml
    adjusted_loss_ml = max(
        raw_water_loss_ml * profile.loss_scale + profile.loss_bias_ml,
        0,
    )

    if input_data.drainage_ml > input_data.water_added_ml:
        warnings.append(
            "배수량이 급수량보다 많습니다. 이전에 저장된 물의 배출 또는 측정 오류를 확인하세요."
        )
    if raw_water_loss_ml < 0:
        warnings.append(
            "원시 수분 손실이 음수입니다. 측정 시점과 화분 무게, 급수·배수량을 확인하세요."
        )
    if input_data.period_days < 2:
        warnings.append("측정 기간이 짧아 하루 평균 손실량의 변동이 클 수 있습니다.")
    elif input_data.period_days > 14:
        warnings.append("측정 기간이 길어 성장 또는 환경 변화가 평균값에 섞였을 수 있습니다.")
    if input_data.end_pot_weight_g > input_data.target_wet_weight_g:
        warnings.append("현재 무게가 젖은 목표 무게보다 큽니다. 배수 완료 여부를 확인하세요.")
    if profile != TuningProfile():
        warnings.append("실험용 보정 계수가 적용된 결과입니다. 프로필 이름과 버전을 함께 기록하세요.")

    average_daily_loss_ml = adjusted_loss_ml / input_data.period_days
    drainage_ratio_percent = (
        input_data.drainage_ml / input_data.water_added_ml * 100
        if input_data.water_added_ml > 0
        else None
    )
    refill_to_target_ml = max(
        (input_data.target_wet_weight_g - input_data.end_pot_weight_g)
        / profile.water_density_g_per_ml,
        0,
    )
    effective_trigger_weight_g = (
        input_data.watering_trigger_weight_g + profile.trigger_margin_g
    )

    if effective_trigger_weight_g >= input_data.target_wet_weight_g:
        raise ValueError("마진이 적용된 물주기 기준 무게는 젖은 목표 무게보다 작아야 합니다.")

    if input_data.end_pot_weight_g <= effective_trigger_weight_g:
        status: WaterStatus = "water_now"
        recommended_now_ml = refill_to_target_ml * profile.recommendation_scale
        days_until_watering = 0.0
    elif input_data.end_pot_weight_g >= input_data.target_wet_weight_g:
        status = "hydrated"
        recommended_now_ml = 0.0
        days_until_watering = (
            (input_data.end_pot_weight_g - effective_trigger_weight_g)
            / profile.water_density_g_per_ml
            / average_daily_loss_ml
            if average_daily_loss_ml > 0
            else None
        )
    else:
        recommended_now_ml = 0.0
        days_until_watering = (
            (input_data.end_pot_weight_g - effective_trigger_weight_g)
            / profile.water_density_g_per_ml
            / average_daily_loss_ml
            if average_daily_loss_ml > 0
            else None
        )
        status = (
            "water_soon"
            if days_until_watering is not None and days_until_watering <= 2
            else "monitor"
        )

    if input_data.max_single_watering_ml is not None:
        recommended_now_ml = min(
            recommended_now_ml,
            input_data.max_single_watering_ml,
        )

    if warnings:
        confidence: Confidence = "low" if raw_water_loss_ml < 0 else "medium"
    elif 2 <= input_data.period_days <= 14:
        confidence = "high"
    else:
        confidence = "medium"

    return LabResult(
        observation_period_days=_rounded(input_data.period_days),
        storage_change_ml=_rounded(storage_change_ml),
        net_water_added_ml=_rounded(net_water_added_ml),
        raw_water_loss_ml=_rounded(raw_water_loss_ml),
        estimated_water_loss_ml=_rounded(adjusted_loss_ml),
        average_daily_loss_ml=_rounded(average_daily_loss_ml),
        drainage_ratio_percent=(
            _rounded(drainage_ratio_percent)
            if drainage_ratio_percent is not None
            else None
        ),
        refill_to_target_ml=_rounded(refill_to_target_ml),
        recommended_water_now_ml=_rounded(recommended_now_ml),
        estimated_days_until_watering=(
            _rounded(days_until_watering)
            if days_until_watering is not None
            else None
        ),
        effective_trigger_weight_g=_rounded(effective_trigger_weight_g),
        status=status,
        confidence=confidence,
        warnings=tuple(warnings),
    )
