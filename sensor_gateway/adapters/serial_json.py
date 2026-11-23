from __future__ import annotations

from dataclasses import dataclass, replace
import json
import sys
import threading
import time
from typing import Callable, Iterable, Optional

from ..models import FieldMapping, RawSample


class SerialDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class SerialPortInfo:
    device: str
    description: str
    manufacturer: Optional[str] = None

    def to_dict(self) -> dict[str, Optional[str]]:
        return {
            "device": self.device,
            "description": self.description,
            "manufacturer": self.manufacturer,
        }


def _load_pyserial():
    try:
        import serial
        from serial.tools import list_ports
    except ImportError as exc:
        raise SerialDependencyError(
            "시리얼 연결에는 pyserial이 필요합니다. "
            "'python -m pip install -r sensor_gateway/requirements.txt'를 실행하세요."
        ) from exc
    return serial, list_ports


def list_serial_ports() -> list[SerialPortInfo]:
    _, list_ports = _load_pyserial()
    return [
        SerialPortInfo(
            device=str(port.device),
            description=str(port.description or ""),
            manufacturer=(str(port.manufacturer) if port.manufacturer else None),
        )
        for port in list_ports.comports()
    ]


def resolve_serial_port(
    requested: str,
    *,
    available: Optional[list[SerialPortInfo]] = None,
) -> str:
    if requested and requested.lower() != "auto":
        return requested
    ports = available if available is not None else list_serial_ports()
    if not ports:
        raise RuntimeError(
            "사용 가능한 시리얼 포트가 없습니다. 아두이노 USB 연결과 드라이버를 확인하세요."
        )
    if len(ports) == 1:
        return ports[0].device
    choices = ", ".join(
        f"{port.device} ({port.description or '설명 없음'})" for port in ports
    )
    raise RuntimeError(
        "시리얼 포트가 여러 개라 자동 선택할 수 없습니다. "
        f"--port로 하나를 지정하세요: {choices}"
    )


class SerialJsonLinesAdapter:
    """Read PlanTalk JSONL directly from an Arduino-compatible serial port."""

    def __init__(
        self,
        *,
        port: str = "auto",
        baud: int = 9600,
        timeout_seconds: float = 2.5,
        reconnect_seconds: float = 3.0,
        mapping: Optional[FieldMapping] = None,
        trust_device_sequence: bool = False,
        max_samples: int = 0,
        serial_factory=None,
        available_ports: Optional[list[SerialPortInfo]] = None,
        diagnostic: Optional[Callable[[str], None]] = None,
        event_callback: Optional[Callable[[str, dict[str, object]], None]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        if baud <= 0:
            raise ValueError("baud는 0보다 커야 합니다.")
        if timeout_seconds <= 0:
            raise ValueError("시리얼 timeout은 0보다 커야 합니다.")
        if reconnect_seconds < 0:
            raise ValueError("재연결 대기시간은 0 이상이어야 합니다.")
        if max_samples < 0:
            raise ValueError("max_samples는 0 이상이어야 합니다.")
        self.requested_port = port
        self.baud = baud
        self.timeout_seconds = timeout_seconds
        self.reconnect_seconds = reconnect_seconds
        self.mapping = mapping or FieldMapping()
        self.trust_device_sequence = trust_device_sequence
        self.max_samples = max_samples
        self.serial_factory = serial_factory
        self.available_ports = available_ports
        self.diagnostic = diagnostic or (
            lambda message: print(f"[serial] {message}", file=sys.stderr)
        )
        self.event_callback = event_callback or (lambda _kind, _details: None)
        self.stop_event = stop_event

    def _should_stop(self) -> bool:
        return self.stop_event is not None and self.stop_event.is_set()

    def _open(self, port: str):
        if self.serial_factory is not None:
            return self.serial_factory(
                port=port,
                baudrate=self.baud,
                timeout=self.timeout_seconds,
            )
        serial, _ = _load_pyserial()
        return serial.Serial(
            port=port,
            baudrate=self.baud,
            timeout=self.timeout_seconds,
        )

    def _parse(self, text: str, port: str) -> Optional[RawSample]:
        line = text.strip()
        if not line or line.startswith("#"):
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            self.diagnostic(f"JSON이 아닌 줄을 건너뜁니다({port}): {exc.msg}")
            return None
        if not isinstance(payload, dict):
            self.diagnostic(f"JSON 객체가 아닌 줄을 건너뜁니다({port}).")
            return None
        try:
            sample = RawSample.from_mapping(payload, self.mapping)
            if not self.trust_device_sequence and sample.sequence_no is not None:
                raw_payload = dict(sample.raw_payload)
                raw_payload["device_sequence_no"] = sample.sequence_no
                sample = replace(
                    sample,
                    sequence_no=None,
                    raw_payload=raw_payload,
                )
            sample.validate()
            return sample
        except (TypeError, ValueError) as exc:
            self.diagnostic(f"유효하지 않은 측정값을 건너뜁니다({port}): {exc}")
            return None

    def __iter__(self) -> Iterable[RawSample]:
        port = resolve_serial_port(
            self.requested_port,
            available=self.available_ports,
        )
        emitted = 0
        while (
            not self._should_stop()
            and (self.max_samples == 0 or emitted < self.max_samples)
        ):
            connection = None
            try:
                connection = self._open(port)
                self.diagnostic(f"{port}에 {self.baud} baud로 연결했습니다.")
                self.event_callback(
                    "serial_connected",
                    {"port": port, "baud": self.baud},
                )
                while (
                    not self._should_stop()
                    and (self.max_samples == 0 or emitted < self.max_samples)
                ):
                    raw_line = connection.readline()
                    if not raw_line:
                        continue
                    if isinstance(raw_line, bytes):
                        text = raw_line.decode("utf-8", errors="replace")
                    else:
                        text = str(raw_line)
                    sample = self._parse(text, port)
                    if sample is None:
                        continue
                    emitted += 1
                    yield sample
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                if self._should_stop():
                    break
                if self.reconnect_seconds == 0:
                    raise RuntimeError(f"시리얼 연결 실패({port}): {exc}") from exc
                self.diagnostic(
                    f"연결이 끊겼습니다({port}): {exc}. "
                    f"{self.reconnect_seconds:g}초 뒤 재연결합니다."
                )
                self.event_callback(
                    "serial_disconnected",
                    {"port": port, "error": str(exc)},
                )
                time.sleep(self.reconnect_seconds)
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass

