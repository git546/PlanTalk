"""Synthetic fixtures: values and thresholds are for software tests, not plant care."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_TIME = datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0)


def make_scenario(key: str, label: str, moisture: int | None, age: int = 5):
    measured = (BASE_TIME - timedelta(minutes=age)).isoformat()
    return {
        "id": key,
        "label": label,
        "source": "synthetic",
        "plant": {"name": "초록이", "species": "스킨답서스"},
        "reference_time": BASE_TIME.isoformat(),
        "timezone": "Asia/Seoul (한국 표준시 KST, UTC+09:00)",
        "note": "모든 수치와 돌봄 기록은 가상. 수분 지수는 실제 수분 함량 %가 아님.",
        "sensors": {
            "soil_moisture": {
                "value": moisture,
                "unit": "index/100",
                "measured_at": measured if moisture is not None else None,
                "measured_at_kst": (
                    (BASE_TIME - timedelta(minutes=age)).strftime("%Y년 %m월 %d일 %H시 %M분 KST")
                    if moisture is not None
                    else "측정 불가"
                ),
                "status": "disconnected" if moisture is None else "ok",
                "test_assessment": "낮음" if moisture == 15 else "판정 없음",
            },
            "illuminance": {"value": 300, "unit": "lx", "measured_at": measured, "status": "ok"},
            "temperature": {"value": 23, "unit": "°C", "measured_at": measured, "status": "ok"},
        },
        "care_records": [
            {"action": "물주기", "at": (BASE_TIME - timedelta(days=3)).isoformat()},
            {"action": "창가로 이동", "at": (BASE_TIME - timedelta(days=1)).isoformat()},
        ],
        "freshness": "이틀 전 측정: 현재 상태를 판단할 수 없음"
        if age > 60
        else "기준 시각 5분 전 측정",
    }


SCENARIOS = {
    "normal": make_scenario("normal", "정상", 50),
    "dry": make_scenario("dry", "건조", 15),
    "stale": make_scenario("stale", "오래된 데이터", 25, 2880),
    "error": make_scenario("error", "센서 오류", None),
}
