from datetime import UTC, datetime

from app.services.chat_time import ChatClock
from app.services.persona import build_system_instruction


def test_seoul_labels_both_sides_of_local_midnight_and_keeps_storage_time():
    clock = ChatClock.from_request("Asia/Seoul", datetime(2026, 11, 26, 16, 0, tzinfo=UTC))
    assert clock.current() == {
        "time_zone": "Asia/Seoul",
        "today": "2026-11-27",
        "local_time": "2026-11-27T01:00+09:00",
    }
    raw_event = {"occurred_at": "2026-11-26T14:30:00+00:00", "event_type": "watering"}
    prompt = build_system_instruction(clock=clock, sensor_context={
        "recent_care_records": {"events": [raw_event]},
        "measured_at": "2026-11-26T15:30:00+00:00",
    })
    assert '"label": "어제 23:30"' in prompt
    assert '"label": "오늘 00:30"' in prompt
    assert '"minutes_ago": 90.0' in prompt
    assert raw_event["occurred_at"] == "2026-11-26T14:30:00+00:00"
    assert raw_event["occurred_at"] not in prompt


def test_unknown_time_zone_falls_back_to_explicit_utc():
    clock = ChatClock.from_request("Asia/unknown", datetime(2026, 11, 26, 16, 0, tzinfo=UTC))
    prompt = build_system_instruction(
        clock=clock, sensor_context={"measured_at": "2026-11-26T15:30:00+00:00"},
    )
    assert '"time_zone": "UTC"' in prompt
    assert '"label": "오늘 15:30 (UTC)"' in prompt
