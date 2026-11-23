"""Input adapters. A real sensor adapter only needs to yield RawSample objects."""

from .json_lines import JsonLinesAdapter
from .serial_json import (
    SerialDependencyError,
    SerialJsonLinesAdapter,
    SerialPortInfo,
    list_serial_ports,
    resolve_serial_port,
)
from .simulator import SimulatorAdapter

__all__ = [
    "JsonLinesAdapter",
    "SerialDependencyError",
    "SerialJsonLinesAdapter",
    "SerialPortInfo",
    "SimulatorAdapter",
    "list_serial_ports",
    "resolve_serial_port",
]

