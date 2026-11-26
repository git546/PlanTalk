from __future__ import annotations

from collections import deque
from datetime import datetime
from statistics import median
from typing import Deque, Optional

from .models import NormalizedMeasurement, RawSample


def _seconds_between(start: str, end: str) -> float:
    return (
        datetime.fromisoformat(end) - datetime.fromisoformat(start)
    ).total_seconds()


def _median_optional(values: list[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    return float(median(present)) if present else None


def _median_payload_number(samples: list[RawSample], key: str) -> Optional[float]:
    values: list[float] = []
    for sample in samples:
        value = sample.raw_payload.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return float(median(values)) if values else None


class StabilityFilter:
    """Convert a rolling window of raw samples into stable representative values."""

    def __init__(
        self,
        *,
        window_size: int,
        max_range_g: float,
        emit_interval_seconds: float,
        firmware_version: Optional[str] = None,
    ) -> None:
        if window_size < 2:
            raise ValueError("window_size는 2 이상이어야 합니다.")
        self.window_size = window_size
        self.max_range_g = max_range_g
        self.emit_interval_seconds = emit_interval_seconds
        self.firmware_version = firmware_version
        self.samples: Deque[RawSample] = deque(maxlen=window_size)
        self.last_emitted_at: Optional[str] = None

    def reset(self) -> None:
        """Discard stale samples after a sensor fault or device restart."""

        self.samples.clear()
        self.last_emitted_at = None

    def push(
        self,
        sample: RawSample,
        *,
        generated_sequence_no: int,
    ) -> Optional[NormalizedMeasurement]:
        if sample.has_nonpositive_weight:
            self.reset()
            return None
        if not sample.has_load_cell_value or sample.sensor_status != "ok":
            return None
        self.samples.append(sample)
        if len(self.samples) < self.window_size:
            return None

        weights = [item.weight_g for item in self.samples]
        if any(weight is None for weight in weights):
            return None
        numeric_weights = [float(weight) for weight in weights if weight is not None]
        stable = max(numeric_weights) - min(numeric_weights) <= self.max_range_g
        if not stable:
            return None

        measured_at = self.samples[-1].captured_at
        if (
            self.last_emitted_at is not None
            and _seconds_between(self.last_emitted_at, measured_at)
            < self.emit_interval_seconds
        ):
            return None

        self.last_emitted_at = measured_at
        latest = self.samples[-1]
        device_sequences = [
            item.sequence_no for item in self.samples if item.sequence_no is not None
        ]
        sequence_no = max(device_sequences) if device_sequences else generated_sequence_no
        sample_window = list(self.samples)
        raw_payload = {
            "window_first_at": self.samples[0].captured_at,
            "window_last_at": measured_at,
            "weight_min_g": min(numeric_weights),
            "weight_max_g": max(numeric_weights),
        }
        soil_raw = _median_payload_number(sample_window, "soil_raw")
        light_raw = _median_payload_number(sample_window, "light_raw")
        if soil_raw is not None:
            raw_payload["soil_raw"] = soil_raw
        if light_raw is not None:
            raw_payload["light_raw"] = light_raw
        for key in ("device_uptime_ms", "device_sequence_no"):
            value = latest.raw_payload.get(key)
            if value is not None:
                raw_payload[key] = value

        return NormalizedMeasurement(
            measured_at=measured_at,
            weight_g=round(float(median(numeric_weights)), 3),
            raw_sensor_value=_median_optional(
                [item.raw_sensor_value for item in self.samples]
            ),
            sequence_no=sequence_no,
            sample_count=len(self.samples),
            is_stable=True,
            temperature_c=_median_optional(
                [item.temperature_c for item in self.samples]
            ),
            humidity_percent=_median_optional(
                [item.humidity_percent for item in self.samples]
            ),
            light_lux=_median_optional([item.light_lux for item in self.samples]),
            light_ppfd=_median_optional([item.light_ppfd for item in self.samples]),
            firmware_version=self.firmware_version,
            raw_payload=raw_payload,
        )

