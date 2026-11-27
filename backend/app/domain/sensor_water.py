from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import combinations
from math import exp
from statistics import median

NOISE_FLOOR_G = 3.0  # Same gram scale as the gateway's default stability window.
STEP_G = 10.0  # Same gram scale as the gateway's default watering-candidate threshold.
NEIGHBORHOOD = timedelta(minutes=30)
MAX_SAMPLE_GAP = timedelta(hours=1)
WATERING_SETTLE_TIME = timedelta(hours=2)
MIN_TREND_SPAN = timedelta(hours=6)


@dataclass(frozen=True)
class WeightPoint:
    at: datetime
    weight_g: float
    soil_raw: float | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    light_ppfd: float | None = None
    light_lux: float | None = None
    light_raw: float | None = None


@dataclass(frozen=True)
class CareRecord:
    at: datetime
    kind: str
    volume_ml: float | None = None


def clean_weight_history(
    points: list[WeightPoint], protected_times: list[datetime],
) -> list[WeightPoint]:
    """Exclude isolated spikes only when both neighboring levels agree."""
    cleaned = []
    for i, point in enumerate(points):
        if (
            i < 2 or i + 2 >= len(points)
            or point.at - points[i - 2].at > NEIGHBORHOOD
            or points[i + 2].at - point.at > NEIGHBORHOOD
            or any(abs(point.at - at) <= NEIGHBORHOOD for at in protected_times)
        ):
            cleaned.append(point)
            continue
        before = [row.weight_g for row in points[i - 2:i]]
        after = [row.weight_g for row in points[i + 1:i + 3]]
        neighbors = before + after
        center = median(neighbors)
        mad = median(abs(value - center) for value in neighbors)
        limit = max(NOISE_FLOOR_G, 3 * 1.4826 * mad)
        if abs(median(before) - median(after)) > NOISE_FLOOR_G or (
            abs(point.weight_g - center) <= limit
        ):
            cleaned.append(point)
    return cleaned


def _hourly_medians(points: list[WeightPoint]) -> list[WeightPoint]:
    hours: dict[datetime, list[WeightPoint]] = defaultdict(list)
    for point in points:
        hours[point.at.replace(minute=0, second=0, microsecond=0)].append(point)
    return [
        WeightPoint(rows[len(rows) // 2].at, median(row.weight_g for row in rows))
        for rows in hours.values()
    ]


def _sensor_evidence(
    points: list[WeightPoint], baseline: list[WeightPoint],
) -> dict[str, object]:
    recent = [point for point in points if points[-1].at - point.at <= NEIGHBORHOOD]
    evidence: dict[str, object] = {}

    # The PlanTalk Uno uses the SEN0193 probe. Larger ADC readings indicate drier soil.
    before = [p.soil_raw for p in baseline if p.soil_raw is not None]
    after = [p.soil_raw for p in recent if p.soil_raw is not None]
    if len(before) >= 3 and len(after) >= 3 and baseline[-1].at < recent[0].at:
        first_soil, last_soil = median(before), median(after)
        change = last_soil - first_soil
        soil_noise = max(
            3.0,
            3 * 1.4826 * median(abs(value - first_soil) for value in before),
            3 * 1.4826 * median(abs(value - last_soil) for value in after),
        )
        direction = "unchanged"
        if abs(change) > soil_noise:
            direction = "drier" if change > 0 else "wetter"
        evidence["soil"] = {
            "trend": direction,
            "baseline_raw": round(first_soil, 2),
            "recent_raw": round(last_soil, 2),
            "change_raw": round(change, 2),
        }

    vpd_values = [
        0.6108 * exp(17.27 * p.temperature_c / (p.temperature_c + 237.3))
        * (1 - p.humidity_percent / 100)
        for p in recent
        if p.temperature_c is not None and p.humidity_percent is not None
    ]
    if vpd_values:
        evidence["air_vpd_kpa"] = round(median(vpd_values), 2)

    for name, read_light in (
        ("ppfd", lambda p: p.light_ppfd),
        ("lux", lambda p: p.light_lux),
        ("raw_adc", lambda p: p.light_raw),
    ):
        recent_light = [value for p in recent if (value := read_light(p)) is not None]
        if recent_light:
            light = {
                "unit": name,
                "recent_median": round(median(recent_light), 2),
            }
            if baseline:
                segment_light = [value for p in points if (value := read_light(p)) is not None]
                light["segment_median"] = round(median(segment_light), 2)
            evidence["light"] = light
            break
    return evidence


def _watering_cycles(
    points: list[WeightPoint], records: list[CareRecord],
) -> list[tuple[WeightPoint, WeightPoint, float | None, float | None]]:
    cycles = []
    for record in records:
        if record.kind != "watering":
            continue
        before_start = record.at - timedelta(minutes=45)
        after_end = record.at + timedelta(hours=2)
        if any(
            other is not record and other.kind == "watering"
            and before_start <= other.at <= after_end for other in records
        ):
            continue
        drained = [
            other for other in records
            if other.kind == "drainage" and record.at <= other.at <= after_end
        ]
        after_start = record.at + timedelta(minutes=45)
        if drained:
            after_start = max(after_start, drained[-1].at + timedelta(minutes=10))
        before = [point for point in points if before_start <= point.at < record.at]
        after = [point for point in points if after_start <= point.at <= after_end]
        if len(before) < 2 or len(after) < 3 or after[-1].at - after[0].at < timedelta(minutes=10):
            continue
        dry = [point.weight_g for point in before]
        wet = [point.weight_g for point in after]
        dry_g = median(dry)
        wet_g = median(wet)
        if (
            max(dry) - min(dry) > NOISE_FLOOR_G
            or max(wet) - min(wet) > NOISE_FLOOR_G
            or wet_g - dry_g < STEP_G
        ):
            continue
        drained_ml = (
            sum(item.volume_ml for item in drained if item.volume_ml is not None)
            if drained and all(item.volume_ml is not None for item in drained)
            else None
        )
        cycles.append((
            WeightPoint(before[-1].at, dry_g), WeightPoint(after[-1].at, wet_g),
            record.volume_ml, drained_ml,
        ))
    return cycles


def assess_sensor_water(
    points: list[WeightPoint],
    care: list[CareRecord],
    *,
    setup_at: datetime | None,
    interrupted_at: datetime | None,
    suspected_watering: datetime | None,
    diagnostics_available: bool,
) -> dict[str, object]:
    """Estimate water lost in the latest uninterrupted weight segment."""
    if not points:
        return {"status": "insufficient_history"}
    points = sorted({point.at: point for point in points}.values(), key=lambda point: point.at)
    records = sorted(care, key=lambda event: event.at)
    protected = [event.at for event in records]
    if suspected_watering is not None:
        protected.append(suspected_watering)
    cleaned = clean_weight_history(points, protected)
    latest = cleaned[-1]
    result: dict[str, object] = {"excluded_isolated_readings": len(points) - len(cleaned)}
    # The latest sample can describe the environment while the weight trend is on hold.
    current_environment = _sensor_evidence([latest], [])
    if current_environment:
        result["sensor_evidence"] = current_environment

    if not diagnostics_available:
        return {**result, "status": "diagnostics_unavailable"}

    recorded = [event for event in records if event.kind == "watering"]
    if recorded:
        last_recorded = recorded[-1]
        result["last_confirmed_watering"] = {
            "occurred_at": last_recorded.at.isoformat(),
            "volume_ml": last_recorded.volume_ml,
        }

    # The water balance of a past event can be described when both volumes were logged.
    for before, after, added_ml, drained_ml in reversed(_watering_cycles(cleaned, records)):
        if (
            added_ml is not None and added_ml > 0 and drained_ml is not None
            and all(at is None or before.at > at for at in (setup_at, interrupted_at))
        ):
            change = after.weight_g - before.weight_g
            loss = added_ml - drained_ml - change
            result["last_recorded_balance"] = {
                "started_at": before.at.isoformat(), "ended_at": after.at.isoformat(),
                "water_added_ml": added_ml, "drainage_ml": drained_ml,
                "measured_storage_change_g": round(change, 2),
                "estimated_water_loss_ml": round(loss, 2) if loss >= 0 else None,
            }
            break

    boundary, source = cleaned[0].at, "first_available_stable_weight"
    for at, reason in ((setup_at, "setup_changed"), (interrupted_at, "collection_interrupted")):
        if at is not None and at >= boundary:
            boundary, source = at, reason
    water_times = [(event.at, event.kind) for event in records]
    if suspected_watering is not None:
        # The home button can follow detection of the same physical event.
        already_recorded = any(
            abs(event.at - suspected_watering) <= NEIGHBORHOOD for event in recorded
        )
        kind = "watering" if already_recorded else "suspected_watering"
        water_times.append((suspected_watering, kind))
    if water_times:
        last_water, kind = max(water_times, key=lambda event: event[0])
        if latest.at < last_water + WATERING_SETTLE_TIME:
            return {**result, "status": "settling_after_watering"}
        if last_water + WATERING_SETTLE_TIME >= boundary:
            boundary, source = last_water + WATERING_SETTLE_TIME, kind

    start = len(cleaned) - 1
    for i in range(start, 0, -1):
        earlier, later = cleaned[i - 1], cleaned[i]
        if earlier.at < boundary:
            break
        if later.at - earlier.at > MAX_SAMPLE_GAP:
            source = "measurement_gap"
            break
        if abs(later.weight_g - earlier.weight_g) >= STEP_G:
            source = "weight_discontinuity"
            break
        start = i - 1

    segment = [point for point in cleaned[start:] if point.at >= boundary]
    for i in range(len(segment) - 2):
        first, middle, last = segment[i:i + 3]
        values = (first.weight_g, middle.weight_g, last.weight_g)
        if last.at - first.at <= NEIGHBORHOOD and max(values) - min(values) <= NOISE_FLOOR_G:
            baseline = WeightPoint(middle.at, median(values))
            baseline_points = [first, middle, last]
            break
    else:
        return {**result, "status": "awaiting_stable_weight"}

    hours = _hourly_medians(segment[i + 1:])
    current = hours[-1]
    change = current.weight_g - baseline.weight_g
    drydown: dict[str, object] = {
        "baseline_source": source,
        "baseline_at": baseline.at.isoformat(),
        "baseline_weight_g": round(baseline.weight_g, 2),
        "comparison_at": current.at.isoformat(),
        "comparison_weight_g": round(current.weight_g, 2),
        "observed_through": segment[-1].at.isoformat(),
        "observed_hours": round((segment[-1].at - baseline.at).total_seconds() / 3600, 2),
        "weight_change_g": round(change, 2),
    }
    result["drydown"] = drydown
    evidence = _sensor_evidence(segment[i:], baseline_points)
    if evidence:
        result["sensor_evidence"] = evidence
    # Bound the slope window so recent dry-down is visible even during a long watering cycle.
    trend = [point for point in hours if latest.at - point.at <= timedelta(days=2)]
    if len(trend) < 5 or trend[-1].at - trend[0].at < MIN_TREND_SPAN:
        return {**result, "status": "insufficient_history"}
    slope = median(
        (b.weight_g - a.weight_g) * 86_400 / (b.at - a.at).total_seconds()
        for a, b in combinations(trend, 2)
    )
    drydown["weight_change_g_per_day"] = round(slope, 2)
    if slope >= 0 or -change <= NOISE_FLOOR_G:
        return {**result, "status": "no_clear_decline"}
    soil = evidence.get("soil")
    soil_trend = soil.get("trend") if isinstance(soil, dict) else None
    if soil_trend == "wetter":
        return {**result, "status": "sensor_disagreement"}
    result["status"] = "drying"
    result["loss_evidence"] = "weight_and_soil" if soil_trend == "drier" else "weight_only"
    result["estimated_replenishment_ml"] = round(-change, 2)  # Water: approximately 1 mL/g.
    return result
