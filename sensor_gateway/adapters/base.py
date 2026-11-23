from __future__ import annotations

from typing import Iterable, Protocol

from ..models import RawSample


class SampleAdapter(Protocol):
    def __iter__(self) -> Iterable[RawSample]:
        ...

