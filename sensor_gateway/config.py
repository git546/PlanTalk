from __future__ import annotations

from dataclasses import dataclass, field, replace
import os
from pathlib import Path
from typing import Mapping, Optional

from .models import FieldMapping, RawSample


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE settings without overriding the process environment."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    value = env.get(key, "").strip()
    return float(value) if value else default


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key, "").strip()
    return int(value) if value else default


def _optional_float(env: Mapping[str, str], key: str) -> Optional[float]:
    value = env.get(key, "").strip()
    return float(value) if value else None


@dataclass(frozen=True)
class GatewayConfig:
    db_path: Path = Path("sensor_gateway/data/gateway.sqlite3")
    plant_id: str = ""
    external_device_id: str = "pot-scale-01"
    device_name: str = "PlanTalk prototype scale"
    hardware_model: Optional[str] = None
    firmware_version: Optional[str] = None
    stability_window_size: int = 20
    stability_max_range_g: float = 3.0
    emit_interval_seconds: float = 60.0
    upload_batch_size: int = 50
    serial_port: str = "auto"
    serial_baud: int = 9600
    serial_timeout_seconds: float = 2.5
    serial_reconnect_seconds: float = 3.0
    raw_zero_value: Optional[float] = None
    raw_grams_per_unit: Optional[float] = None
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    supabase_email: str = ""
    supabase_password: str = ""
    mapping: FieldMapping = field(default_factory=FieldMapping)

    @classmethod
    def from_environment(
        cls,
        env: Optional[Mapping[str, str]] = None,
    ) -> "GatewayConfig":
        env = env or os.environ
        return cls(
            db_path=Path(
                env.get(
                    "GATEWAY_DB_PATH",
                    "sensor_gateway/data/gateway.sqlite3",
                )
            ),
            plant_id=env.get("GATEWAY_PLANT_ID", "").strip(),
            external_device_id=env.get(
                "GATEWAY_DEVICE_ID",
                "pot-scale-01",
            ).strip(),
            device_name=env.get(
                "GATEWAY_DEVICE_NAME",
                "PlanTalk prototype scale",
            ).strip(),
            hardware_model=env.get("GATEWAY_HARDWARE_MODEL") or None,
            firmware_version=env.get("GATEWAY_FIRMWARE_VERSION") or None,
            stability_window_size=_int(env, "GATEWAY_STABILITY_WINDOW", 20),
            stability_max_range_g=_float(
                env,
                "GATEWAY_STABILITY_MAX_RANGE_G",
                3.0,
            ),
            emit_interval_seconds=_float(
                env,
                "GATEWAY_EMIT_INTERVAL_SECONDS",
                60.0,
            ),
            upload_batch_size=_int(env, "GATEWAY_UPLOAD_BATCH_SIZE", 50),
            serial_port=env.get("GATEWAY_SERIAL_PORT", "auto").strip() or "auto",
            serial_baud=_int(env, "GATEWAY_SERIAL_BAUD", 9600),
            serial_timeout_seconds=_float(
                env,
                "GATEWAY_SERIAL_TIMEOUT_SECONDS",
                2.5,
            ),
            serial_reconnect_seconds=_float(
                env,
                "GATEWAY_SERIAL_RECONNECT_SECONDS",
                3.0,
            ),
            raw_zero_value=_optional_float(env, "GATEWAY_RAW_ZERO_VALUE"),
            raw_grams_per_unit=_optional_float(
                env,
                "GATEWAY_RAW_GRAMS_PER_UNIT",
            ),
            supabase_url=env.get("SUPABASE_URL", "").rstrip("/"),
            supabase_publishable_key=(
                env.get("SUPABASE_PUBLISHABLE_KEY")
                or env.get("SUPABASE_ANON_KEY")
                or ""
            ).strip(),
            supabase_email=env.get("SUPABASE_TEST_EMAIL", "").strip(),
            supabase_password=env.get("SUPABASE_TEST_PASSWORD", ""),
            mapping=FieldMapping(
                timestamp=env.get("GATEWAY_FIELD_TIMESTAMP", "measured_at"),
                weight_g=env.get("GATEWAY_FIELD_WEIGHT", "weight_g"),
                raw_value=env.get(
                    "GATEWAY_FIELD_RAW_VALUE",
                    "raw_sensor_value",
                ),
                sequence_no=env.get(
                    "GATEWAY_FIELD_SEQUENCE",
                    "sequence_no",
                ),
                temperature_c=env.get(
                    "GATEWAY_FIELD_TEMPERATURE",
                    "temperature_c",
                ),
                humidity_percent=env.get(
                    "GATEWAY_FIELD_HUMIDITY",
                    "humidity_percent",
                ),
                light_lux=env.get("GATEWAY_FIELD_LIGHT_LUX", "light_lux"),
                light_ppfd=env.get(
                    "GATEWAY_FIELD_LIGHT_PPFD",
                    "light_ppfd",
                ),
                sensor_status=env.get("GATEWAY_FIELD_STATUS", "status"),
                hx711_ready=env.get(
                    "GATEWAY_FIELD_HX711_READY",
                    "hx711_ready",
                ),
            ),
        )

    def validate_local(self) -> None:
        if not self.external_device_id:
            raise ValueError("GATEWAY_DEVICE_ID가 필요합니다.")
        if self.stability_window_size < 2:
            raise ValueError("GATEWAY_STABILITY_WINDOW는 2 이상이어야 합니다.")
        if self.stability_max_range_g < 0:
            raise ValueError("GATEWAY_STABILITY_MAX_RANGE_G는 0 이상이어야 합니다.")
        if self.emit_interval_seconds < 0:
            raise ValueError("GATEWAY_EMIT_INTERVAL_SECONDS는 0 이상이어야 합니다.")
        if self.serial_baud <= 0:
            raise ValueError("GATEWAY_SERIAL_BAUD는 0보다 커야 합니다.")
        if self.serial_timeout_seconds <= 0:
            raise ValueError("GATEWAY_SERIAL_TIMEOUT_SECONDS는 0보다 커야 합니다.")
        if self.serial_reconnect_seconds < 0:
            raise ValueError("GATEWAY_SERIAL_RECONNECT_SECONDS는 0 이상이어야 합니다.")
        if self.raw_grams_per_unit == 0:
            raise ValueError("GATEWAY_RAW_GRAMS_PER_UNIT는 0이 아니어야 합니다.")
        if (self.raw_zero_value is None) != (self.raw_grams_per_unit is None):
            raise ValueError(
                "원시값 변환에는 GATEWAY_RAW_ZERO_VALUE와 "
                "GATEWAY_RAW_GRAMS_PER_UNIT가 모두 필요합니다."
            )

    def validate_remote(self) -> None:
        self.validate_local()
        required = {
            "GATEWAY_PLANT_ID": self.plant_id,
            "SUPABASE_URL": self.supabase_url,
            "SUPABASE_PUBLISHABLE_KEY": self.supabase_publishable_key,
            "SUPABASE_TEST_EMAIL": self.supabase_email,
            "SUPABASE_TEST_PASSWORD": self.supabase_password,
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError(f"원격 전송 설정이 누락됐습니다: {', '.join(missing)}")

    def safe_summary(self) -> dict[str, object]:
        return {
            "db_path": str(self.db_path),
            "plant_id_configured": bool(self.plant_id),
            "external_device_id": self.external_device_id,
            "stability_window_size": self.stability_window_size,
            "stability_max_range_g": self.stability_max_range_g,
            "emit_interval_seconds": self.emit_interval_seconds,
            "serial_port": self.serial_port,
            "serial_baud": self.serial_baud,
            "raw_calibration_configured": (
                self.raw_zero_value is not None
                and self.raw_grams_per_unit is not None
            ),
            "supabase_configured": bool(
                self.supabase_url and self.supabase_publishable_key
            ),
            "login_configured": bool(
                self.supabase_email and self.supabase_password
            ),
        }

    def apply_raw_calibration(self, sample: RawSample) -> RawSample:
        """Fill weight_g from a raw load-cell value when coefficients are known."""

        if sample.weight_g is not None:
            return sample
        if (
            sample.raw_sensor_value is None
            or self.raw_zero_value is None
            or self.raw_grams_per_unit is None
        ):
            return sample
        weight_g = (
            sample.raw_sensor_value - self.raw_zero_value
        ) * self.raw_grams_per_unit
        return replace(sample, weight_g=round(weight_g, 3))

