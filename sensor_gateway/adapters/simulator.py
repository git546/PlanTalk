from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random
import time
from typing import Iterable

from ..models import RawSample


class SimulatorAdapter:
    """Generate repeatable load-cell-like samples for gateway testing."""

    def __init__(
        self,
        *,
        count: int = 120,
        interval_seconds: float = 1.0,
        start_weight_g: float = 3800.0,
        daily_loss_g: float = 80.0,
        noise_g: float = 0.6,
        seed: int = 42,
        sleep: bool = False,
    ) -> None:
        if count < 1:
            raise ValueError("count는 1 이상이어야 합니다.")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds는 0보다 커야 합니다.")
        self.count = count
        self.interval_seconds = interval_seconds
        self.start_weight_g = start_weight_g
        self.daily_loss_g = daily_loss_g
        self.noise_g = noise_g
        self.seed = seed
        self.sleep = sleep

    def __iter__(self) -> Iterable[RawSample]:
        randomizer = random.Random(self.seed)
        started_at = datetime.now(timezone.utc)
        loss_per_second = self.daily_loss_g / 86_400
        for index in range(self.count):
            elapsed_seconds = index * self.interval_seconds
            measured_at = started_at + timedelta(seconds=elapsed_seconds)
            weight = (
                self.start_weight_g
                - loss_per_second * elapsed_seconds
                + randomizer.gauss(0, self.noise_g)
            )
            raw_value = weight * 220 + randomizer.gauss(0, 20)
            yield RawSample(
                captured_at=measured_at.isoformat(timespec="milliseconds"),
                weight_g=round(weight, 3),
                raw_sensor_value=round(raw_value, 3),
                sequence_no=index + 1,
                temperature_c=24.0,
                humidity_percent=55.0,
                light_lux=12000.0,
                raw_payload={"simulated": True, "index": index},
            )
            if self.sleep:
                time.sleep(self.interval_seconds)

