from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from queue import Empty, Queue
from statistics import median
import threading
from typing import Iterable, Iterator, Optional

from ..adapters import SerialJsonLinesAdapter, list_serial_ports
from ..cli import calculate_calibration
from ..models import RawSample
from ..service import GatewayService
from ..storage import GatewayStore
from ..supabase_client import SupabaseGatewayClient
from .config_file import load_config, update_env


@dataclass(frozen=True)
class UiEvent:
    kind: str
    payload: object


class ObservingAdapter:
    def __init__(self, samples: Iterable[RawSample], callback) -> None:
        self.samples = samples
        self.callback = callback

    def __iter__(self) -> Iterator[RawSample]:
        for sample in self.samples:
            self.callback(sample)
            yield sample


class GatewayController:
    def __init__(self) -> None:
        self.events: Queue[UiEvent] = Queue()
        self.stop_event = threading.Event()
        self.worker: Optional[threading.Thread] = None

    def emit(self, kind: str, payload: object) -> None:
        self.events.put(UiEvent(kind, payload))

    def drain_events(self) -> list[UiEvent]:
        items: list[UiEvent] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except Empty:
                return items

    def available_ports(self) -> list[dict[str, Optional[str]]]:
        return [port.to_dict() for port in list_serial_ports()]

    def run_async(self, target, *args) -> bool:
        if self.worker is not None and self.worker.is_alive():
            return False

        def wrapped() -> None:
            try:
                target(*args)
            except Exception as exc:
                self.emit("error", str(exc))
            finally:
                self.emit("idle", None)

        self.worker = threading.Thread(target=wrapped, daemon=True)
        self.worker.start()
        return True

    def measure_raw(self, port: str, count: int = 20) -> float:
        self.emit("log", f"{port}에서 원본값 {count}개를 측정합니다.")
        adapter = SerialJsonLinesAdapter(
            port=port,
            baud=9600,
            reconnect_seconds=0,
            # Opening an Arduino port commonly produces one boot/status record.
            # Allow extra valid records, but finish only after `count` load-cell
            # values have actually been collected.
            max_samples=count + 10,
            diagnostic=lambda message: self.emit("log", message),
        )
        values: list[float] = []
        for sample in adapter:
            if sample.raw_sensor_value is not None:
                values.append(sample.raw_sensor_value)
                self.emit(
                    "sample",
                    {
                        "raw_sensor_value": sample.raw_sensor_value,
                        "weight_g": None,
                        "soil_raw": sample.raw_payload.get("soil_raw"),
                        "light_raw": sample.raw_payload.get("light_raw"),
                        "temperature_c": sample.temperature_c,
                        "humidity_percent": sample.humidity_percent,
                        "sensor_status": sample.sensor_status,
                        "hx711_ready": sample.hx711_ready,
                    },
                )
                if len(values) >= count:
                    break
        if len(values) < count:
            raise RuntimeError("로드셀 원본값을 충분히 받지 못했습니다.")
        result = float(median(values))
        self.emit("measurement", result)
        return result

    def save_calibration(
        self,
        *,
        zero_raw: float,
        loaded_raw: float,
        known_weight_g: float,
    ) -> dict[str, float]:
        result = calculate_calibration(
            zero_raw=zero_raw,
            loaded_raw=loaded_raw,
            known_weight_g=known_weight_g,
        )
        update_env(
            {
                "GATEWAY_RAW_ZERO_VALUE": f"{result['zero_raw']:.10g}",
                "GATEWAY_RAW_GRAMS_PER_UNIT": (
                    f"{result['grams_per_unit']:.12g}"
                ),
            }
        )
        self.emit("calibration", result)
        self.emit("log", "로드셀 보정값을 로컬 설정에 저장했습니다.")
        return result

    def test_remote(self) -> None:
        config = load_config()
        config.validate_remote()
        client = SupabaseGatewayClient(config)
        client.login()
        self.emit("remote_ok", True)
        self.emit("log", "Supabase 테스트 계정 로그인을 확인했습니다.")

    def start_collection(self, port: str, upload: bool) -> bool:
        self.stop_event.clear()
        return self.run_async(self._collect, port, upload)

    def _collect(self, port: str, upload: bool) -> None:
        config = replace(load_config(), serial_port=port, serial_baud=9600)
        config.validate_remote() if upload else config.validate_local()
        store = GatewayStore(config.db_path)
        uploader = SupabaseGatewayClient(config) if upload else None
        service = GatewayService(config, store, uploader)

        adapter = SerialJsonLinesAdapter(
            port=port,
            baud=9600,
            timeout_seconds=config.serial_timeout_seconds,
            reconnect_seconds=config.serial_reconnect_seconds,
            mapping=config.mapping,
            stop_event=self.stop_event,
            diagnostic=lambda message: self.emit("log", message),
            event_callback=service.record_transport_event,
        )

        def observe(sample: RawSample) -> None:
            converted = config.apply_raw_calibration(sample)
            self.emit(
                "sample",
                {
                    "raw_sensor_value": converted.raw_sensor_value,
                    "weight_g": converted.weight_g,
                    "soil_raw": converted.raw_payload.get("soil_raw"),
                    "light_raw": converted.raw_payload.get("light_raw"),
                    "temperature_c": converted.temperature_c,
                    "humidity_percent": converted.humidity_percent,
                    "captured_at": converted.captured_at,
                    "sensor_status": converted.sensor_status,
                    "hx711_ready": converted.hx711_ready,
                },
            )

        self.emit("running", {"port": port, "upload": upload})
        summary = service.run(ObservingAdapter(adapter, observe), upload=upload)
        self.emit("summary", asdict(summary))

    def stop_collection(self) -> None:
        self.stop_event.set()
        self.emit("log", "수집 중지를 요청했습니다. 최대 몇 초 후 종료됩니다.")

