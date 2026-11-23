from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def normalize_timestamp(value: Any) -> str:
    """Return a timezone-aware ISO timestamp, assuming UTC only when omitted."""

    if value is None or str(value).strip() == "":
        return utc_now_iso()
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _optional_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return True
    if text in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"불리언 값으로 해석할 수 없습니다: {value}")


def get_path(data: Mapping[str, Any], path: Optional[str]) -> Any:
    """Read a dot-separated key path from arbitrary JSON."""

    if not path:
        return None
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


@dataclass(frozen=True)
class FieldMapping:
    timestamp: str = "measured_at"
    weight_g: str = "weight_g"
    raw_value: str = "raw_sensor_value"
    sequence_no: str = "sequence_no"
    temperature_c: str = "temperature_c"
    humidity_percent: str = "humidity_percent"
    light_lux: str = "light_lux"
    light_ppfd: str = "light_ppfd"
    sensor_status: str = "status"
    hx711_ready: str = "hx711_ready"


@dataclass(frozen=True)
class RawSample:
    captured_at: str
    weight_g: Optional[float]
    raw_sensor_value: Optional[float] = None
    sequence_no: Optional[int] = None
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    light_lux: Optional[float] = None
    light_ppfd: Optional[float] = None
    sensor_status: str = "ok"
    hx711_ready: Optional[bool] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
        mapping: Optional[FieldMapping] = None,
    ) -> "RawSample":
        mapping = mapping or FieldMapping()
        weight_g = _optional_float(get_path(payload, mapping.weight_g))
        raw_sensor_value = _optional_float(get_path(payload, mapping.raw_value))
        status_value = get_path(payload, mapping.sensor_status)
        sensor_status = (
            str(status_value).strip()
            if status_value is not None and str(status_value).strip()
            else "ok"
        )
        return cls(
            captured_at=normalize_timestamp(get_path(payload, mapping.timestamp)),
            weight_g=weight_g,
            raw_sensor_value=raw_sensor_value,
            sequence_no=_optional_int(get_path(payload, mapping.sequence_no)),
            temperature_c=_optional_float(get_path(payload, mapping.temperature_c)),
            humidity_percent=_optional_float(
                get_path(payload, mapping.humidity_percent)
            ),
            light_lux=_optional_float(get_path(payload, mapping.light_lux)),
            light_ppfd=_optional_float(get_path(payload, mapping.light_ppfd)),
            sensor_status=sensor_status,
            hx711_ready=_optional_bool(get_path(payload, mapping.hx711_ready)),
            raw_payload=dict(payload),
        )

    @property
    def has_load_cell_value(self) -> bool:
        return self.weight_g is not None or self.raw_sensor_value is not None

    def validate(self) -> None:
        if not self.sensor_status.strip():
            raise ValueError("status는 빈 문자열일 수 없습니다.")
        if not self.has_load_cell_value and self.sensor_status == "ok":
            raise ValueError(
                "정상 측정에는 weight_g 또는 raw_sensor_value 중 하나가 필요합니다."
            )
        if self.sensor_status == "ok" and self.hx711_ready is False:
            raise ValueError("status=ok인데 hx711_ready=false일 수 없습니다.")
        if self.weight_g is not None and self.weight_g <= 0:
            raise ValueError("weight_g는 0보다 커야 합니다.")
        if self.humidity_percent is not None and not 0 <= self.humidity_percent <= 100:
            raise ValueError("humidity_percent는 0~100 범위여야 합니다.")
        if self.light_lux is not None and self.light_lux < 0:
            raise ValueError("light_lux는 0 이상이어야 합니다.")
        if self.light_ppfd is not None and self.light_ppfd < 0:
            raise ValueError("light_ppfd는 0 이상이어야 합니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedMeasurement:
    measured_at: str
    weight_g: float
    sequence_no: int
    raw_sensor_value: Optional[float]
    sample_count: int
    is_stable: bool
    temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    light_lux: Optional[float] = None
    light_ppfd: Optional[float] = None
    firmware_version: Optional[str] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CareEvent:
    event_type: str
    occurred_at: str
    external_event_id: str
    volume_ml: Optional[float] = None
    weight_g: Optional[float] = None
    notes: Optional[str] = None

    def validate(self) -> None:
        if self.event_type not in {
            "watering",
            "drainage",
            "calibration",
            "setup_changed",
        }:
            raise ValueError("지원하지 않는 돌봄 이벤트입니다.")
        if self.volume_ml is not None and self.volume_ml < 0:
            raise ValueError("volume_ml은 0 이상이어야 합니다.")
        if self.weight_g is not None and self.weight_g <= 0:
            raise ValueError("weight_g는 0보다 커야 합니다.")
        if (
            self.event_type in {"watering", "drainage"}
            and self.volume_ml is None
            and self.weight_g is None
        ):
            raise ValueError("급수·배수 이벤트에는 volume_ml 또는 weight_g가 필요합니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GatewayEvent:
    event_type: str
    occurred_at: str
    external_event_id: str
    severity: str = "info"
    details: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.event_type.strip():
            raise ValueError("게이트웨이 이벤트 종류가 필요합니다.")
        if self.severity not in {"info", "warning", "error"}:
            raise ValueError("severity는 info, warning, error 중 하나여야 합니다.")
        if not self.external_event_id.strip():
            raise ValueError("게이트웨이 이벤트 ID가 필요합니다.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

