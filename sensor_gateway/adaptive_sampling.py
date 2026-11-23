from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .models import NormalizedMeasurement


def _seconds_between(start: str, end: str) -> float:
    return (
        datetime.fromisoformat(end) - datetime.fromisoformat(start)
    ).total_seconds()


@dataclass(frozen=True)
class SamplingDecision:
    should_emit: bool
    mode: str
    watering_details: Optional[dict[str, object]] = None


class AdaptiveSamplingPolicy:
    """Throttle stable measurements and temporarily increase sampling after watering."""

    def __init__(
        self,
        *,
        routine_interval_seconds: float,
        watering_detection_enabled: bool,
        watering_min_increase_g: float,
        watering_confirm_seconds: float,
        watering_burst_interval_seconds: float,
        watering_burst_duration_seconds: float,
    ) -> None:
        self.routine_interval_seconds = routine_interval_seconds
        self.watering_detection_enabled = watering_detection_enabled
        self.watering_min_increase_g = watering_min_increase_g
        self.watering_confirm_seconds = watering_confirm_seconds
        self.watering_burst_interval_seconds = watering_burst_interval_seconds
        self.watering_burst_duration_seconds = watering_burst_duration_seconds
        self.last_emitted_at: Optional[str] = None
        self.baseline_weight_g: Optional[float] = None
        self.pending_since: Optional[str] = None
        self.pending_baseline_weight_g: Optional[float] = None
        self.pending_peak_weight_g: Optional[float] = None
        self.burst_until: Optional[str] = None

    def reset(self) -> None:
        """Discard state after a device restart, sensor fault, or collection gap."""

        self.last_emitted_at = None
        self.baseline_weight_g = None
        self.pending_since = None
        self.pending_baseline_weight_g = None
        self.pending_peak_weight_g = None
        self.burst_until = None

    def _burst_active(self, measured_at: str) -> bool:
        if self.burst_until is None:
            return False
        return datetime.fromisoformat(measured_at) <= datetime.fromisoformat(
            self.burst_until
        )

    def _start_burst(self, measured_at: str) -> None:
        end = datetime.fromisoformat(measured_at) + timedelta(
            seconds=self.watering_burst_duration_seconds
        )
        self.burst_until = end.isoformat(timespec="milliseconds")

    def observe(self, measurement: NormalizedMeasurement) -> SamplingDecision:
        measured_at = measurement.measured_at
        weight_g = measurement.weight_g
        watering_details: Optional[dict[str, object]] = None
        was_in_burst = self._burst_active(measured_at)

        if self.baseline_weight_g is None:
            self.baseline_weight_g = weight_g

        if not was_in_burst and self.watering_detection_enabled:
            self.baseline_weight_g = min(self.baseline_weight_g, weight_g)
            increase_g = weight_g - self.baseline_weight_g
            if increase_g >= self.watering_min_increase_g:
                if self.pending_since is None:
                    self.pending_since = measured_at
                    self.pending_baseline_weight_g = self.baseline_weight_g
                    self.pending_peak_weight_g = weight_g
                else:
                    self.pending_peak_weight_g = max(
                        self.pending_peak_weight_g or weight_g,
                        weight_g,
                    )
                    if (
                        _seconds_between(self.pending_since, measured_at)
                        >= self.watering_confirm_seconds
                    ):
                        baseline = self.pending_baseline_weight_g
                        peak = self.pending_peak_weight_g
                        assert baseline is not None
                        assert peak is not None
                        watering_details = {
                            "baseline_weight_g": round(baseline, 3),
                            "detected_weight_g": round(weight_g, 3),
                            "peak_weight_g": round(peak, 3),
                            "increase_g": round(weight_g - baseline, 3),
                            "confirmation_seconds": round(
                                _seconds_between(self.pending_since, measured_at),
                                3,
                            ),
                            "detection": "stable_weight_increase",
                        }
                        self._start_burst(measured_at)
                        self.baseline_weight_g = weight_g
                        self.pending_since = None
                        self.pending_baseline_weight_g = None
                        self.pending_peak_weight_g = None
            else:
                self.pending_since = None
                self.pending_baseline_weight_g = None
                self.pending_peak_weight_g = None
        elif was_in_burst:
            self.baseline_weight_g = min(self.baseline_weight_g, weight_g)

        in_burst = self._burst_active(measured_at)
        mode = "watering_burst" if in_burst else "routine"
        interval = (
            self.watering_burst_interval_seconds
            if in_burst
            else self.routine_interval_seconds
        )
        should_emit = watering_details is not None or self.last_emitted_at is None
        if not should_emit and self.last_emitted_at is not None:
            should_emit = (
                _seconds_between(self.last_emitted_at, measured_at) >= interval
            )
        if should_emit:
            self.last_emitted_at = measured_at
        return SamplingDecision(
            should_emit=should_emit,
            mode=mode,
            watering_details=watering_details,
        )
