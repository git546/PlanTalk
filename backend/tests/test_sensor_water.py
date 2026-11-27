from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.domain.sensor_water import (
    CareRecord,
    WeightPoint,
    assess_sensor_water,
    clean_weight_history,
)

START = datetime(2026, 11, 20, tzinfo=UTC)
OPTIONS = {
    "setup_at": None,
    "interrupted_at": None,
    "suspected_watering": None,
    "diagnostics_available": True,
}


def time_at(minute: int) -> datetime:
    return START + timedelta(minutes=minute)


def test_detect_isolated_spike_without_flattening_a_persistent_step():
    weights = [350, 350, 240, 350, 350, 380, 380, 380, 380]
    points = [WeightPoint(time_at(i * 10), g) for i, g in enumerate(weights)]
    assert [p.weight_g for p in clean_weight_history(points, [])] == weights[:2] + weights[3:]
    assert clean_weight_history(points, [points[2].at]) == points


def weight_series(start: int, minutes: int, weight: float, loss_per_hour: float = 1):
    return [
        WeightPoint(time_at(start + minute), weight - minute * loss_per_hour / 60)
        for minute in range(0, minutes + 1, 10)
    ]


def test_uses_first_stable_weight_to_measure_loss_without_target_or_drainage():
    summary = assess_sensor_water(weight_series(0, 480, 390), [], **OPTIONS)
    assert summary["status"] == "drying"
    assert summary["drydown"]["baseline_at"] == time_at(10).isoformat()
    assert summary["drydown"]["baseline_weight_g"] == 389.83
    assert summary["drydown"]["weight_change_g_per_day"] == -24
    assert summary["drydown"]["weight_change_g"] == -7.83
    assert summary["estimated_replenishment_ml"] == 7.83
    assert "watering_trigger_weight_g" not in summary
    assert "last_recorded_balance" not in summary


def test_recent_weight_jump_waits_for_a_second_reading():
    points = [WeightPoint(time_at(i * 10), g) for i, g in enumerate([380, 380, 340])]
    summary = assess_sensor_water(points, [], **OPTIONS)
    assert summary["status"] == "awaiting_stable_weight"
    assert "estimated_replenishment_ml" not in summary


def test_recorded_watering_restarts_the_segment_and_keeps_the_recorded_amount():
    points = [
        *weight_series(0, 50, 350, 0),
        *weight_series(110, 50, 376, 0),
        *weight_series(200, 480, 376),
    ]
    care = [CareRecord(time_at(60), "watering", 50), CareRecord(time_at(75), "drainage", 5)]
    summary = assess_sensor_water(points, care, **OPTIONS)
    assert summary["status"] == "drying"
    assert summary["last_confirmed_watering"]["volume_ml"] == 50
    assert summary["last_recorded_balance"]["estimated_water_loss_ml"] == 19
    assert summary["drydown"]["baseline_source"] == "drainage"
    assert summary["drydown"]["baseline_at"] == time_at(210).isoformat()
    assert summary["estimated_replenishment_ml"] == 7.67


def test_suspected_watering_waits_for_settling_then_requires_a_decline():
    points = weight_series(0, 180, 350)
    options = {**OPTIONS, "suspected_watering": time_at(190)}
    after = weight_series(190, 70, 380, 0)
    after[-1] = replace(after[-1], temperature_c=25, humidity_percent=50, light_raw=310)
    settling = assess_sensor_water(points + after, [], **options)
    assert settling["status"] == "settling_after_watering"
    assert settling["sensor_evidence"]["air_vpd_kpa"] == 1.58
    assert settling["sensor_evidence"]["light"]["unit"] == "raw_adc"
    assert "last_confirmed_watering" not in settling

    flat = assess_sensor_water([*points, *weight_series(310, 480, 380, 0)], [], **options)
    assert flat["status"] == "no_clear_decline"
    assert flat["drydown"]["baseline_source"] == "suspected_watering"
    assert "estimated_replenishment_ml" not in flat


def test_gap_and_reset_do_not_include_earlier_weight_loss():
    before = weight_series(0, 480, 390)
    later = weight_series(600, 60, 370)
    gap = assess_sensor_water(before + later, [], **OPTIONS)
    assert gap["status"] == "insufficient_history"
    assert gap["drydown"]["baseline_source"] == "measurement_gap"
    assert gap["drydown"]["baseline_weight_g"] == 369.83
    assert "estimated_replenishment_ml" not in gap

    reset = assess_sensor_water(
        weight_series(0, 480, 390), [], **{**OPTIONS, "interrupted_at": time_at(360)}
    )
    assert reset["drydown"]["baseline_source"] == "collection_interrupted"
    assert reset["drydown"]["baseline_at"] == time_at(370).isoformat()
    assert "estimated_replenishment_ml" not in reset


def test_auxiliary_sensors_corroborate_or_hold_the_weight_estimate():
    points = weight_series(0, 480, 390)
    for direction, status, soil_trend in [
        (1, "drying", "drier"), (-1, "sensor_disagreement", "wetter"),
    ]:
        readings = [
            replace(
                point, soil_raw=300 + i / 2 * direction, temperature_c=25,
                humidity_percent=50, light_raw=300, light_lux=500,
            )
            for i, point in enumerate(points)
        ]
        result = assess_sensor_water(readings, [], **OPTIONS)
        assert result["status"] == status
        evidence = result["sensor_evidence"]
        assert evidence["soil"]["trend"] == soil_trend
        assert evidence["air_vpd_kpa"] == 1.58
        assert evidence["light"] == {
            "unit": "lux", "recent_median": 500, "segment_median": 500,
        }
        if direction == 1:
            assert result["loss_evidence"] == "weight_and_soil"
            assert result["estimated_replenishment_ml"] == 7.83
        else:
            assert "estimated_replenishment_ml" not in result
