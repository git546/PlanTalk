from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

RECORD_TIME_FIELDS = {
    "measured_at", "occurred_at", "baseline_at", "comparison_at",
    "observed_through", "started_at", "ended_at", "estimated_from_at",
}


def parse_record_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else None


@dataclass(frozen=True)
class ChatClock:
    now: datetime
    zone: ZoneInfo | timezone

    @classmethod
    def from_request(cls, time_zone: str | None, now: datetime) -> "ChatClock":
        if not time_zone:
            return cls(now=now, zone=UTC)
        try:
            zone = ZoneInfo(time_zone)
        except (ValueError, ZoneInfoNotFoundError):
            zone = UTC
        return cls(now=now, zone=zone)

    @property
    def zone_name(self) -> str:
        return self.zone.key if isinstance(self.zone, ZoneInfo) else "UTC"

    def current(self) -> dict[str, str]:
        local = self.now.astimezone(self.zone)
        return {
            "time_zone": self.zone_name,
            "today": local.date().isoformat(),
            "local_time": local.isoformat(timespec="minutes"),
        }

    def localize_records(self, value: object) -> object:
        """Label times for the provider without changing the stored timestamps."""
        if isinstance(value, list):
            return [self.localize_records(item) for item in value]
        if not isinstance(value, dict):
            return value
        return {
            key: self._describe(timestamp)
            if key in RECORD_TIME_FIELDS and (timestamp := parse_record_time(item)) is not None
            else self.localize_records(item)
            for key, item in value.items()
        }

    def _describe(self, timestamp: datetime) -> dict[str, str | float]:
        local = timestamp.astimezone(self.zone)
        days_ago = (self.now.astimezone(self.zone).date() - local.date()).days
        day_label = {0: "오늘", 1: "어제"}.get(days_ago, local.date().isoformat())
        return {
            "local_time": local.isoformat(timespec="minutes"),
            "label": f"{day_label} {local:%H:%M}" + (" (UTC)" if self.zone_name == "UTC" else ""),
            "minutes_ago": round((self.now - timestamp).total_seconds() / 60, 1),
        }
