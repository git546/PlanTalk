from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Callable, Iterable, Optional, Protocol
from uuid import uuid4

from .adaptive_sampling import AdaptiveSamplingPolicy
from .config import GatewayConfig
from .models import (
    CareEvent,
    GatewayEvent,
    NormalizedMeasurement,
    RawSample,
    utc_now_iso,
)
from .stability import StabilityFilter
from .storage import GatewayStore


class RemoteUploader(Protocol):
    def upload_measurement(self, measurement: NormalizedMeasurement) -> None:
        ...

    def upload_care_event(self, event: CareEvent) -> None:
        ...

    def upload_gateway_event(self, event: GatewayEvent) -> None:
        ...


@dataclass(frozen=True)
class RunSummary:
    raw_samples: int
    status_samples: int
    normalized_measurements: int
    duplicates_ignored: int
    upload_sent: int
    upload_failed: int


class GatewayService:
    def __init__(
        self,
        config: GatewayConfig,
        store: GatewayStore,
        uploader: Optional[RemoteUploader] = None,
        *,
        diagnostic: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.config = config
        self.store = store
        self.uploader = uploader
        self.diagnostic = diagnostic
        self.filter = StabilityFilter(
            window_size=config.stability_window_size,
            max_range_g=config.stability_max_range_g,
            emit_interval_seconds=0,
            firmware_version=config.firmware_version,
        )
        self.sampling_policy = AdaptiveSamplingPolicy(
            routine_interval_seconds=config.emit_interval_seconds,
            watering_detection_enabled=config.watering_detection_enabled,
            watering_min_increase_g=config.watering_min_increase_g,
            watering_confirm_seconds=config.watering_confirm_seconds,
            watering_burst_interval_seconds=(
                config.watering_burst_interval_seconds
            ),
            watering_burst_duration_seconds=(
                config.watering_burst_duration_seconds
            ),
        )

    def _reset_sampling(self) -> None:
        self.filter.reset()
        self.sampling_policy.reset()

    def record_gateway_event(
        self,
        event_type: str,
        *,
        severity: str = "info",
        occurred_at: Optional[str] = None,
        details: Optional[dict[str, object]] = None,
    ) -> bool:
        event = GatewayEvent(
            event_type=event_type,
            occurred_at=occurred_at or utc_now_iso(),
            external_event_id=f"{event_type}-{uuid4().hex}",
            severity=severity,
            details=dict(details or {}),
        )
        return self.store.enqueue_gateway_event(
            self.config.external_device_id,
            event,
        )

    def record_transport_event(
        self,
        event_type: str,
        details: dict[str, object],
    ) -> None:
        severity = "warning" if event_type == "serial_disconnected" else "info"
        self.record_gateway_event(
            event_type,
            severity=severity,
            details=details,
        )

    @staticmethod
    def _payload_number(sample: RawSample, key: str) -> Optional[float]:
        value = sample.raw_payload.get(key)
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _track_device_state(self, sample: RawSample) -> int:
        """Persist transition events that explain otherwise silent gaps."""

        device_id = self.config.external_device_id
        prefix = f"device_state:{device_id}:"
        previous_uptime_text = self.store.get_metadata(prefix + "uptime_ms")
        previous_time = self.store.get_metadata(prefix + "captured_at")
        previous_status = self.store.get_metadata(prefix + "status")
        uptime_ms = self._payload_number(sample, "device_uptime_ms")
        created = 0

        if uptime_ms is not None and previous_uptime_text and previous_time:
            previous_uptime = float(previous_uptime_text)
            wall_gap = (
                datetime.fromisoformat(sample.captured_at)
                - datetime.fromisoformat(previous_time)
            ).total_seconds()
            uptime_gap = (uptime_ms - previous_uptime) / 1000.0
            gap_threshold = max(self.config.serial_timeout_seconds * 3, 10.0)
            details = {
                "wall_gap_seconds": round(wall_gap, 3),
                "uptime_gap_seconds": round(uptime_gap, 3),
                "previous_uptime_ms": previous_uptime,
                "current_uptime_ms": uptime_ms,
            }
            if uptime_gap < 0 and sample.sensor_status != "boot":
                created += int(
                    self.record_gateway_event(
                        "arduino_restart_detected",
                        severity="warning",
                        occurred_at=sample.captured_at,
                        details=details,
                    )
                )
                self._reset_sampling()
            elif wall_gap > gap_threshold and uptime_gap < wall_gap * 0.25:
                created += int(
                    self.record_gateway_event(
                        "collection_gap_power_or_restart",
                        severity="warning",
                        occurred_at=sample.captured_at,
                        details=details,
                    )
                )
                self._reset_sampling()
            elif wall_gap > gap_threshold and uptime_gap > wall_gap * 0.75:
                created += int(
                    self.record_gateway_event(
                        "collection_gap_device_running",
                        severity="warning",
                        occurred_at=sample.captured_at,
                        details=details,
                    )
                )

        if sample.sensor_status == "boot":
            created += int(
                self.record_gateway_event(
                    "arduino_boot",
                    occurred_at=sample.captured_at,
                    details={
                        "device_uptime_ms": uptime_ms,
                        "hx711_ready": sample.hx711_ready,
                    },
                )
            )
            self._reset_sampling()

        if sample.sensor_status != previous_status:
            if sample.sensor_status == "hx711_not_ready":
                created += int(
                    self.record_gateway_event(
                        "hx711_not_ready",
                        severity="error",
                        occurred_at=sample.captured_at,
                        details={"device_uptime_ms": uptime_ms},
                    )
                )
                self._reset_sampling()
            elif previous_status == "hx711_not_ready" and sample.sensor_status == "ok":
                created += int(
                    self.record_gateway_event(
                        "hx711_recovered",
                        occurred_at=sample.captured_at,
                        details={"device_uptime_ms": uptime_ms},
                    )
                )
                self._reset_sampling()

        if uptime_ms is not None:
            self.store.set_metadata(prefix + "uptime_ms", str(uptime_ms))
        self.store.set_metadata(prefix + "captured_at", sample.captured_at)
        self.store.set_metadata(prefix + "status", sample.sensor_status)
        return created

    def run(self, samples: Iterable[RawSample], upload: bool = False) -> RunSummary:
        raw_count = 0
        status_count = 0
        normalized_count = 0
        duplicates = 0
        sent = 0
        failed = 0
        waiting_for_positive_weight = False
        self.record_gateway_event("gateway_run_started")
        try:
            for sample in samples:
                sample = self.config.apply_raw_calibration(sample)
                sample.validate()
                self.store.append_raw(self.config.external_device_id, sample)
                raw_count += 1
                self._track_device_state(sample)
                generated_sequence = self.store.next_sequence(
                    self.config.external_device_id
                )
                nonpositive_weight = sample.has_nonpositive_weight
                if sample.sensor_status == "ok" and sample.weight_g is not None:
                    if nonpositive_weight and not waiting_for_positive_weight:
                        self.record_gateway_event(
                            "weight_nonpositive",
                            severity="warning",
                            occurred_at=sample.captured_at,
                            details={"weight_g": sample.weight_g},
                        )
                        if self.diagnostic:
                            self.diagnostic(
                                "보정 무게가 0g 이하입니다. 화분과 영점을 확인해 주세요. "
                                "센서 수집은 계속합니다."
                            )
                    elif waiting_for_positive_weight and not nonpositive_weight:
                        self.record_gateway_event(
                            "weight_recovered", occurred_at=sample.captured_at,
                        )
                        if self.diagnostic:
                            self.diagnostic("양수 무게를 다시 수신했습니다. 안정값을 계산합니다.")
                    waiting_for_positive_weight = nonpositive_weight

                if (
                    nonpositive_weight
                    or not sample.has_load_cell_value
                    or sample.sensor_status != "ok"
                ):
                    status_count += 1
                    self._reset_sampling()
                    if upload and self.uploader is not None:
                        batch_sent, batch_failed = self.flush_outbox()
                        sent += batch_sent
                        failed += batch_failed
                    continue
                measurement = self.filter.push(
                    sample,
                    generated_sequence_no=generated_sequence,
                )
                if measurement is None:
                    continue
                decision = self.sampling_policy.observe(measurement)
                if decision.watering_details is not None:
                    self.record_gateway_event(
                        "watering_suspected",
                        occurred_at=measurement.measured_at,
                        details={
                            **decision.watering_details,
                            "threshold_g": self.config.watering_min_increase_g,
                            "burst_interval_seconds": (
                                self.config.watering_burst_interval_seconds
                            ),
                            "burst_duration_seconds": (
                                self.config.watering_burst_duration_seconds
                            ),
                        },
                    )
                if not decision.should_emit:
                    continue
                measurement = replace(
                    measurement,
                    raw_payload={
                        **measurement.raw_payload,
                        "sampling_mode": decision.mode,
                    },
                )
                if self.store.enqueue_measurement(
                    self.config.external_device_id,
                    measurement,
                ):
                    normalized_count += 1
                else:
                    duplicates += 1
                if upload and self.uploader is not None:
                    batch_sent, batch_failed = self.flush_outbox()
                    sent += batch_sent
                    failed += batch_failed
        finally:
            self.record_gateway_event("gateway_run_stopped")
        if upload and self.uploader is not None:
            batch_sent, batch_failed = self.flush_outbox()
            sent += batch_sent
            failed += batch_failed
        return RunSummary(
            raw_samples=raw_count,
            status_samples=status_count,
            normalized_measurements=normalized_count,
            duplicates_ignored=duplicates,
            upload_sent=sent,
            upload_failed=failed,
        )

    def record_event(self, event: CareEvent, upload: bool = False) -> bool:
        created = self.store.enqueue_care_event(
            self.config.external_device_id,
            event,
        )
        if upload and self.uploader is not None:
            self.flush_outbox()
        return created

    def flush_outbox(self) -> tuple[int, int]:
        if self.uploader is None:
            raise RuntimeError("원격 업로더가 설정되지 않았습니다.")
        sent = 0
        failed = 0
        for item in self.store.pending(self.config.upload_batch_size):
            try:
                if item.kind == "measurement":
                    self.uploader.upload_measurement(
                        NormalizedMeasurement(**item.payload)
                    )
                elif item.kind == "care_event":
                    self.uploader.upload_care_event(CareEvent(**item.payload))
                elif item.kind == "gateway_event":
                    self.uploader.upload_gateway_event(GatewayEvent(**item.payload))
                else:
                    raise ValueError(f"알 수 없는 outbox 종류: {item.kind}")
            except Exception as exc:
                failed += 1
                self.store.mark_failed(
                    item.id,
                    item.attempts + 1,
                    str(exc),
                )
                if item.kind != "gateway_event":
                    break
            else:
                self.store.mark_sent(item.id)
                sent += 1
        return sent, failed

