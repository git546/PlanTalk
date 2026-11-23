from __future__ import annotations

import json
from typing import Iterable, TextIO

from ..models import FieldMapping, RawSample


class JsonLinesAdapter:
    """Read one JSON object per line from stdin, a pipe, or a replay file."""

    def __init__(
        self,
        stream: TextIO,
        mapping: FieldMapping | None = None,
    ) -> None:
        self.stream = stream
        self.mapping = mapping or FieldMapping()

    def __iter__(self) -> Iterable[RawSample]:
        for line_number, raw_line in enumerate(self.stream, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"JSONL {line_number}번째 줄을 읽을 수 없습니다: {exc.msg}"
                ) from exc
            if not isinstance(payload, dict):
                raise ValueError(
                    f"JSONL {line_number}번째 줄은 JSON 객체여야 합니다."
                )
            sample = RawSample.from_mapping(payload, self.mapping)
            sample.validate()
            yield sample

