from __future__ import annotations

from dataclasses import replace
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sensor_gateway.adapters import (
    JsonLinesAdapter,
    SerialJsonLinesAdapter,
    SerialPortInfo,
    SimulatorAdapter,
    resolve_serial_port,
)
from sensor_gateway.adaptive_sampling import AdaptiveSamplingPolicy
from sensor_gateway.cli import calculate_calibration
from sensor_gateway.config import GatewayConfig
from sensor_gateway.desktop.controller import GatewayController
from sensor_gateway.models import CareEvent, FieldMapping, RawSample
from sensor_gateway.service import GatewayService
from sensor_gateway.stability import StabilityFilter
from sensor_gateway.storage import GatewayStore


class FakeUploader:
    def __init__(self) -> None:
        self.measurements = []
        self.events = []
        self.gateway_events = []

    def upload_measurement(self, measurement) -> None:
        self.measurements.append(measurement)

    def upload_care_event(self, event) -> None:
        self.events.append(event)

    def upload_gateway_event(self, event) -> None:
        self.gateway_events.append(event)


class FakeSerial:
    def __init__(self, lines) -> None:
        self.lines = iter(lines)
        self.closed = False

    def readline(self):
        return next(self.lines)

    def close(self) -> None:
        self.closed = True


class GatewayTests(unittest.TestCase):
    def test_calibration_ignores_boot_record_and_collects_raw_values(self) -> None:
        samples = [
            RawSample(
                captured_at="2026-11-25T00:00:00+00:00",
                weight_g=None,
                sensor_status="boot",
                hx711_ready=False,
            )
        ]
        samples.extend(
            RawSample(
                captured_at=f"2026-11-25T00:00:{index:02d}+00:00",
                weight_g=None,
                raw_sensor_value=float(100 + index),
                sensor_status="ok",
                hx711_ready=True,
            )
            for index in range(1, 21)
        )
        controller = GatewayController()
        with patch(
            "sensor_gateway.desktop.controller.SerialJsonLinesAdapter",
            return_value=samples,
        ) as adapter_class:
            result = controller.measure_raw("COM3", count=20)
        self.assertEqual(result, 110.5)
        self.assertEqual(adapter_class.call_args.kwargs["max_samples"], 30)

    @staticmethod
    def _measurement(at: str, weight_g: float, sequence_no: int):
        from sensor_gateway.models import NormalizedMeasurement

        return NormalizedMeasurement(
            measured_at=at,
            weight_g=weight_g,
            sequence_no=sequence_no,
            raw_sensor_value=None,
            sample_count=20,
            is_stable=True,
        )

    def test_adaptive_policy_uses_routine_interval(self) -> None:
        policy = AdaptiveSamplingPolicy(
            routine_interval_seconds=600,
            watering_detection_enabled=False,
            watering_min_increase_g=10,
            watering_confirm_seconds=30,
            watering_burst_interval_seconds=60,
            watering_burst_duration_seconds=1800,
        )
        first = policy.observe(
            self._measurement("2026-11-24T00:00:00+00:00", 1000, 1)
        )
        early = policy.observe(
            self._measurement("2026-11-24T00:09:59+00:00", 999, 2)
        )
        due = policy.observe(
            self._measurement("2026-11-24T00:10:00+00:00", 998, 3)
        )
        self.assertTrue(first.should_emit)
        self.assertFalse(early.should_emit)
        self.assertTrue(due.should_emit)

    def test_adaptive_policy_detects_watering_and_enters_burst(self) -> None:
        policy = AdaptiveSamplingPolicy(
            routine_interval_seconds=600,
            watering_detection_enabled=True,
            watering_min_increase_g=10,
            watering_confirm_seconds=30,
            watering_burst_interval_seconds=60,
            watering_burst_duration_seconds=1800,
        )
        baseline = policy.observe(
            self._measurement("2026-11-24T00:00:00+00:00", 1000, 1)
        )
        pending = policy.observe(
            self._measurement("2026-11-24T00:01:00+00:00", 1012, 2)
        )
        confirmed = policy.observe(
            self._measurement("2026-11-24T00:01:30+00:00", 1013, 3)
        )
        burst_early = policy.observe(
            self._measurement("2026-11-24T00:02:00+00:00", 1011, 4)
        )
        burst_due = policy.observe(
            self._measurement("2026-11-24T00:02:30+00:00", 1010, 5)
        )
        self.assertTrue(baseline.should_emit)
        self.assertFalse(pending.should_emit)
        self.assertTrue(confirmed.should_emit)
        self.assertEqual(confirmed.mode, "watering_burst")
        self.assertIsNotNone(confirmed.watering_details)
        assert confirmed.watering_details is not None
        self.assertEqual(confirmed.watering_details["increase_g"], 13)
        self.assertFalse(burst_early.should_emit)
        self.assertTrue(burst_due.should_emit)

    def test_nested_json_mapping(self) -> None:
        stream = StringIO(
            '{"data":{"time":"2026-11-13T12:30:00Z",'
            '"scale":{"grams":3548.7,"raw":788240}}}\n'
        )
        mapping = FieldMapping(
            timestamp="data.time",
            weight_g="data.scale.grams",
            raw_value="data.scale.raw",
        )
        sample = next(iter(JsonLinesAdapter(stream, mapping)))
        self.assertEqual(sample.weight_g, 3548.7)
        self.assertEqual(sample.raw_sensor_value, 788240.0)
        self.assertTrue(sample.captured_at.endswith("+00:00"))

    def test_serial_adapter_adds_pc_time_and_uses_gateway_sequence(self) -> None:
        connection = FakeSerial(
            [
                b"# boot message\r\n",
                (
                    b'{"sequence_no":1,"device_uptime_ms":2041,'
                    b'"raw_sensor_value":824530,"soil_raw":491,'
                    b'"light_raw":720,"temperature_c":23.4,'
                    b'"humidity_percent":51.0}\r\n'
                ),
            ]
        )
        adapter = SerialJsonLinesAdapter(
            available_ports=[SerialPortInfo("COM3", "Arduino Uno")],
            serial_factory=lambda **_: connection,
            reconnect_seconds=0,
            max_samples=1,
            diagnostic=lambda _: None,
        )
        sample = next(iter(adapter))
        self.assertTrue(sample.captured_at.endswith("+00:00"))
        self.assertIsNone(sample.sequence_no)
        self.assertEqual(sample.raw_payload["device_sequence_no"], 1)
        self.assertEqual(sample.raw_payload["soil_raw"], 491)
        self.assertEqual(sample.raw_payload["light_raw"], 720)

    def test_hx711_fault_json_is_preserved_as_status_sample(self) -> None:
        stream = StringIO(
            '{"sequence_no":2,"device_uptime_ms":4041,'
            '"status":"hx711_not_ready","hx711_ready":false,'
            '"raw_sensor_value":null,"soil_raw":491}\n'
        )
        sample = next(iter(JsonLinesAdapter(stream)))
        self.assertEqual(sample.sensor_status, "hx711_not_ready")
        self.assertFalse(sample.hx711_ready)
        self.assertFalse(sample.has_load_cell_value)

    def test_serial_auto_port_requires_unambiguous_port(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "여러 개"):
            resolve_serial_port(
                "auto",
                available=[
                    SerialPortInfo("COM3", "Arduino Uno"),
                    SerialPortInfo("COM5", "USB Serial"),
                ],
            )

    def test_calibration_supports_decreasing_raw_values(self) -> None:
        result = calculate_calibration(
            zero_raw=350000,
            loaded_raw=100000,
            known_weight_g=1000,
        )
        self.assertEqual(result["grams_per_unit"], -0.004)

    def test_raw_value_can_be_converted_without_sensor_adapter(self) -> None:
        config = GatewayConfig(
            raw_zero_value=100000,
            raw_grams_per_unit=0.01,
        )
        converted = config.apply_raw_calibration(
            RawSample(
                captured_at="2026-11-13T12:30:00+00:00",
                weight_g=None,
                raw_sensor_value=350000,
            )
        )
        self.assertEqual(converted.weight_g, 2500.0)

    def test_decreasing_raw_value_can_use_negative_calibration(self) -> None:
        config = GatewayConfig(
            raw_zero_value=350000,
            raw_grams_per_unit=-0.01,
        )
        config.validate_local()
        converted = config.apply_raw_calibration(
            RawSample(
                captured_at="2026-11-13T06:00:00+00:00",
                weight_g=None,
                raw_sensor_value=100000,
            )
        )
        self.assertEqual(converted.weight_g, 2500.0)

    def test_stability_filter_emits_median(self) -> None:
        stability = StabilityFilter(
            window_size=3,
            max_range_g=2.0,
            emit_interval_seconds=0,
        )
        result = None
        for index, weight in enumerate((1000.5, 999.8, 1000.0), start=1):
            result = stability.push(
                RawSample(
                    captured_at=f"2026-11-13T12:30:0{index}+00:00",
                    weight_g=weight,
                    sequence_no=index,
                    raw_payload={
                        "soil_raw": 490 + index,
                        "light_raw": 700 + index,
                        "device_uptime_ms": index * 2000,
                    },
                ),
                generated_sequence_no=index,
            )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.weight_g, 1000.0)
        self.assertEqual(result.sample_count, 3)
        self.assertEqual(result.sequence_no, 3)
        self.assertEqual(result.raw_payload["soil_raw"], 492.0)
        self.assertEqual(result.raw_payload["light_raw"], 702.0)
        self.assertEqual(result.raw_payload["device_uptime_ms"], 6000)

    def test_unstable_window_is_not_emitted(self) -> None:
        stability = StabilityFilter(
            window_size=3,
            max_range_g=1.0,
            emit_interval_seconds=0,
        )
        result = None
        for index, weight in enumerate((1000.0, 1010.0, 999.0), start=1):
            result = stability.push(
                RawSample(
                    captured_at=f"2026-11-13T12:30:0{index}+00:00",
                    weight_g=weight,
                ),
                generated_sequence_no=index,
            )
        self.assertIsNone(result)

    def test_status_sample_resets_stability_window(self) -> None:
        stability = StabilityFilter(
            window_size=2,
            max_range_g=1.0,
            emit_interval_seconds=0,
        )
        first = RawSample(
            captured_at="2026-11-13T12:30:00+00:00",
            weight_g=1000.0,
        )
        fault = RawSample(
            captured_at="2026-11-13T12:30:02+00:00",
            weight_g=None,
            sensor_status="hx711_not_ready",
            hx711_ready=False,
        )
        self.assertIsNone(stability.push(first, generated_sequence_no=1))
        stability.reset()
        self.assertIsNone(stability.push(fault, generated_sequence_no=2))
        self.assertIsNone(stability.push(first, generated_sequence_no=3))

    def test_store_keeps_raw_and_idempotent_outbox(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = GatewayStore(Path(temp_dir) / "gateway.sqlite3")
            sample = next(
                iter(
                    SimulatorAdapter(
                        count=1,
                        interval_seconds=1,
                        noise_g=0,
                    )
                )
            )
            store.append_raw("device-1", sample)
            filter_ = StabilityFilter(
                window_size=2,
                max_range_g=1,
                emit_interval_seconds=0,
            )
            filter_.push(sample, generated_sequence_no=1)
            measurement = filter_.push(
                replace(sample, sequence_no=2),
                generated_sequence_no=2,
            )
            assert measurement is not None
            self.assertTrue(store.enqueue_measurement("device-1", measurement))
            self.assertFalse(store.enqueue_measurement("device-1", measurement))
            self.assertEqual(store.stats()["raw_samples"], 1)
            self.assertEqual(store.stats()["outbox_pending"], 1)

    def test_service_flushes_measurement_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = GatewayConfig(
                db_path=Path(temp_dir) / "gateway.sqlite3",
                external_device_id="device-1",
                stability_window_size=3,
                stability_max_range_g=5,
                emit_interval_seconds=0,
            )
            store = GatewayStore(config.db_path)
            uploader = FakeUploader()
            service = GatewayService(config, store, uploader)
            summary = service.run(
                SimulatorAdapter(
                    count=5,
                    interval_seconds=1,
                    noise_g=0,
                ),
                upload=True,
            )
            self.assertGreaterEqual(summary.normalized_measurements, 1)
            self.assertGreaterEqual(len(uploader.measurements), 1)
            self.assertGreaterEqual(len(uploader.gateway_events), 1)

            event = CareEvent(
                event_type="watering",
                occurred_at="2026-11-13T13:00:00+00:00",
                external_event_id="watering-1",
                volume_ml=300,
            )
            self.assertTrue(service.record_event(event, upload=True))
            self.assertEqual(len(uploader.events), 1)
            self.assertEqual(store.stats()["outbox_pending"], 0)

    def test_service_records_hx711_fault_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = GatewayConfig(
                db_path=Path(temp_dir) / "gateway.sqlite3",
                external_device_id="device-1",
                stability_window_size=2,
                stability_max_range_g=5,
                emit_interval_seconds=0,
            )
            store = GatewayStore(config.db_path)
            samples = [
                RawSample(
                    captured_at="2026-11-13T12:30:00+00:00",
                    weight_g=None,
                    sensor_status="boot",
                    hx711_ready=False,
                    raw_payload={"device_uptime_ms": 0},
                ),
                RawSample(
                    captured_at="2026-11-13T12:30:02+00:00",
                    weight_g=None,
                    sensor_status="hx711_not_ready",
                    hx711_ready=False,
                    raw_payload={"device_uptime_ms": 2000},
                ),
                RawSample(
                    captured_at="2026-11-13T12:30:04+00:00",
                    weight_g=1000.0,
                    sensor_status="ok",
                    hx711_ready=True,
                    raw_payload={"device_uptime_ms": 4000},
                ),
                RawSample(
                    captured_at="2026-11-13T12:30:06+00:00",
                    weight_g=1000.1,
                    sensor_status="ok",
                    hx711_ready=True,
                    raw_payload={"device_uptime_ms": 6000},
                ),
            ]
            summary = GatewayService(config, store).run(samples)
            self.assertEqual(summary.status_samples, 2)
            self.assertEqual(summary.normalized_measurements, 1)
            event_types = {
                row["event_type"] for row in store.recent_gateway_events(20)
            }
            self.assertIn("arduino_boot", event_types)
            self.assertIn("hx711_not_ready", event_types)
            self.assertIn("hx711_recovered", event_types)

    def test_service_records_suspected_watering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = GatewayConfig(
                db_path=Path(temp_dir) / "gateway.sqlite3",
                external_device_id="device-1",
                stability_window_size=2,
                stability_max_range_g=2,
                emit_interval_seconds=600,
                watering_detection_enabled=True,
                watering_min_increase_g=10,
                watering_confirm_seconds=2,
                watering_burst_interval_seconds=60,
                watering_burst_duration_seconds=1800,
            )
            store = GatewayStore(config.db_path)
            samples = [
                RawSample(
                    captured_at="2026-11-24T00:00:00+00:00",
                    weight_g=1000,
                ),
                RawSample(
                    captured_at="2026-11-24T00:00:02+00:00",
                    weight_g=1000,
                ),
                RawSample(
                    captured_at="2026-11-24T00:00:04+00:00",
                    weight_g=1015,
                ),
                RawSample(
                    captured_at="2026-11-24T00:00:06+00:00",
                    weight_g=1015,
                ),
                RawSample(
                    captured_at="2026-11-24T00:00:08+00:00",
                    weight_g=1015,
                ),
            ]
            summary = GatewayService(config, store).run(samples)
            event_types = {
                row["event_type"] for row in store.recent_gateway_events(20)
            }
            self.assertIn("watering_suspected", event_types)
            self.assertEqual(summary.normalized_measurements, 2)


if __name__ == "__main__":
    unittest.main()

