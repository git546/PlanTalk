from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MeasurementSource = Literal["manual", "simulator", "device"]


class WaterBalanceRequest(BaseModel):
    period_days: float = Field(gt=0, le=90)
    start_pot_weight_g: float = Field(gt=0)
    end_pot_weight_g: float = Field(gt=0)
    water_added_ml: float = Field(ge=0)
    drainage_ml: float = Field(ge=0)
    target_wet_weight_g: float = Field(gt=0)
    watering_trigger_weight_g: float = Field(gt=0)
    max_single_watering_ml: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_weight_thresholds(self) -> "WaterBalanceRequest":
        if self.watering_trigger_weight_g >= self.target_wet_weight_g:
            raise ValueError("물주기 기준 무게는 충분히 젖은 목표 무게보다 작아야 합니다.")
        return self


class WeightMeasurement(BaseModel):
    """A normalized weight reading, independent of a specific load-cell vendor."""

    measured_at: datetime
    weight_g: float = Field(gt=0)
    source: MeasurementSource = "manual"
    device_id: str | None = Field(default=None, min_length=1, max_length=100)
    sequence_no: int | None = Field(default=None, ge=0)
    is_stable: bool = True
    raw_sensor_value: float | None = None
    sample_count: int | None = Field(default=None, ge=1)

    @field_validator("measured_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("측정 시각에는 시간대 정보가 필요합니다.")
        return value

    @model_validator(mode="after")
    def require_device_identity(self) -> "WeightMeasurement":
        if self.source == "device" and not self.device_id:
            raise ValueError("실제 기기 측정값에는 device_id가 필요합니다.")
        return self


class EnvironmentSnapshot(BaseModel):
    temperature_c: float | None = None
    humidity_percent: float | None = Field(default=None, ge=0, le=100)
    light_lux: float | None = Field(default=None, ge=0)
    light_ppfd: float | None = Field(default=None, ge=0)


class WaterCalibrationProfile(BaseModel):
    setup_weight_g: float = Field(gt=0)
    target_wet_weight_g: float = Field(gt=0)
    watering_trigger_weight_g: float = Field(gt=0)
    max_single_watering_ml: float | None = Field(default=None, gt=0)
    calibrated_at: datetime | None = None
    version: int = Field(default=1, ge=1)

    @field_validator("calibrated_at")
    @classmethod
    def require_calibration_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("보정 시각에는 시간대 정보가 필요합니다.")
        return value

    @model_validator(mode="after")
    def validate_weight_thresholds(self) -> "WaterCalibrationProfile":
        if self.watering_trigger_weight_g >= self.target_wet_weight_g:
            raise ValueError("물주기 기준 무게는 충분히 젖은 목표 무게보다 작아야 합니다.")
        return self


class WaterBalanceEvaluationRequest(BaseModel):
    """Device-ready request using timestamped measurements and an explicit calibration."""

    plant_id: str = Field(min_length=1, max_length=100)
    calibration: WaterCalibrationProfile
    start_measurement: WeightMeasurement
    end_measurement: WeightMeasurement
    water_added_ml: float = Field(ge=0)
    drainage_ml: float = Field(ge=0)
    environment: EnvironmentSnapshot | None = None

    @model_validator(mode="after")
    def validate_measurement_window(self) -> "WaterBalanceEvaluationRequest":
        if self.end_measurement.measured_at <= self.start_measurement.measured_at:
            raise ValueError("종료 측정 시각은 시작 측정 시각보다 늦어야 합니다.")
        elapsed_days = (
            self.end_measurement.measured_at - self.start_measurement.measured_at
        ).total_seconds() / 86_400
        if elapsed_days > 90:
            raise ValueError("한 번의 측정 구간은 90일을 넘을 수 없습니다.")
        return self


class WaterBalanceTrace(BaseModel):
    calculation_version: Literal["water-balance-rules-v1"] = "water-balance-rules-v1"
    input_mode: Literal["legacy", "measurement_window"]
    measurement_sources: list[MeasurementSource]
    started_at: datetime | None = None
    ended_at: datetime | None = None
    device_ids: list[str] = Field(default_factory=list)


class WaterBalanceResponse(BaseModel):
    observation_period_days: float
    storage_change_ml: float
    net_water_added_ml: float
    estimated_water_loss_ml: float
    average_daily_loss_ml: float
    drainage_ratio_percent: float | None
    refill_to_target_ml: float
    recommended_water_now_ml: float
    estimated_days_until_watering: float | None
    status: Literal["hydrated", "monitor", "water_soon", "water_now"]
    confidence: Literal["low", "medium", "high"]
    warnings: list[str]
    assumption: str = "화분 무게 1g의 변화는 물 1mL의 변화로 근사했습니다."
    trace: WaterBalanceTrace
