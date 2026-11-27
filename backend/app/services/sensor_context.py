import asyncio
import logging
from datetime import UTC, datetime, timedelta
from math import isfinite

import httpx

from app.core.config import Settings
from app.domain.sensor_water import CareRecord, WeightPoint, assess_sensor_water
from app.services.chat_time import parse_record_time
from app.services.supabase_data import DataStoreError, _base_url, _headers

logger = logging.getLogger(__name__)
FRESH_FOR = timedelta(hours=1)
HISTORY_WINDOW = timedelta(hours=24)
CALIBRATION_WINDOW = timedelta(days=14)
RECENT_CARE_LIMIT = 6
COLLECTION_RESETS = (
    "arduino_boot",
    "arduino_restart_detected",
    "collection_gap_power_or_restart",
    "gateway_run_stopped",
    "serial_disconnected",
)
INTERRUPTIONS = (*COLLECTION_RESETS, "hx711_not_ready", "weight_nonpositive")
SENSOR_RANGES = {
    "temperature_c": (-40, 80),
    "humidity_percent": (0, 100),
    "light_lux": (0, 250_000),
    "light_ppfd": (0, 4_000),
    "soil_raw": (1, 1022),
    "light_raw": (0, 1023),
}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _sensor_values(row: dict) -> dict[str, float | None]:
    payload = row.get("raw_payload")
    payload = payload if isinstance(payload, dict) else {}
    values = {}
    for name, (lower, upper) in SENSOR_RANGES.items():
        value = _number(row.get(name, payload.get(name)))
        values[name] = value if value is not None and lower <= value <= upper else None
    return values


def _inferred_watering_records(
    rows: list[dict] | None, start: datetime, now: datetime,
) -> dict[str, object]:
    records = []
    for row in rows or []:
        detected = parse_record_time(row.get("occurred_at"))
        if detected is None or not start <= detected <= now:
            continue
        earliest = parse_record_time(row.get("estimated_from_at"))
        increase = _number(row.get("observed_weight_increase_g"))
        records.append({
            "source": "sensor",
            "occurred_at": detected.isoformat(),
            "estimated_from_at": (
                earliest.isoformat() if earliest is not None and earliest < detected else None
            ),
            "observed_weight_increase_g": (
                increase if increase is not None and increase > 0 else None
            ),
        })
    return {"status": "available" if rows is not None else "unavailable", "events": records}


async def _save_sensor_assessment(
    base_url: str, headers: dict[str, str], payload: dict,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                f"{base_url}/rpc/save_plant_water_assessment", headers=headers, json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("Could not save plant water assessment")


async def load_sensor_context(
    plant_id: str | None,
    access_token: str,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict[str, object] | None:
    """Evaluate and save observations for an already resolved plant with the user's session."""
    if not plant_id or not access_token:
        return None
    now = now if now is not None else datetime.now(UTC)
    since = now - HISTORY_WINDOW
    history_start = now - CALIBRATION_WINDOW

    try:
        base_url = _base_url(settings)
        headers = _headers(settings, access_token)
    except DataStoreError:
        return {
            "status": "unavailable",
            "recent_care_records": {"status": "unavailable"},
            "watering_history": {
                "direct": {"status": "unavailable"}, "inferred": {"status": "unavailable"},
            },
        }

    async with httpx.AsyncClient(timeout=3) as client:
        async def read_rows(table: str, **params: str) -> list[dict] | None:
            try:
                response = await client.get(
                    f"{base_url}/{table}",
                    headers=headers,
                    params={"plant_id": f"eq.{plant_id}", **params},
                )
                response.raise_for_status()
                rows = response.json()
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    return rows
            except (httpx.HTTPError, ValueError):
                pass
            logger.warning("Could not load chat sensor context from %s", table)
            return None

        care_bounds = (
            f"(occurred_at.gte.{history_start.isoformat()},occurred_at.lte.{now.isoformat()})"
        )
        measurements, care, inferred = await asyncio.gather(
            read_rows(
                "weight_measurements",
                select=(
                    "device_id,calibration_id,measured_at,weight_g,temperature_c,humidity_percent,"
                    "light_lux,light_ppfd,raw_payload"
                ),
                source="eq.device",
                is_stable="eq.true",
                order="measured_at.desc,id.desc",
                limit="10",
                **{
                    "and": (
                        f"(measured_at.gte.{since.isoformat()},"
                        f"measured_at.lte.{now.isoformat()})"
                    ),
                },
            ),
            read_rows(
                "care_events",
                select="device_id,event_type,occurred_at,volume_ml,source",
                source="in.(manual,device)",
                event_type="in.(watering,drainage,setup_changed,calibration)",
                order="occurred_at.desc,id.desc",
                limit="300",
                **{"and": care_bounds},
            ),
            read_rows(
                "plant_watering_records",
                select="occurred_at,estimated_from_at,observed_weight_increase_g",
                record_kind="eq.inferred",
                order="occurred_at.desc,source_record_id.desc",
                limit=str(RECENT_CARE_LIMIT),
                **{"and": care_bounds},
            ),
        )
        recent_events = []
        direct_watering = []
        for row in care or []:
            at = parse_record_time(row.get("occurred_at"))
            kind, source = row.get("event_type"), row.get("source")
            if (
                at is None or not history_start <= at <= now
                or kind not in ("watering", "drainage", "setup_changed", "calibration")
                or source not in ("manual", "device")
            ):
                continue
            volume = _number(row.get("volume_ml"))
            record = {
                "event_type": kind,
                "source": source,
                "occurred_at": at.isoformat(),
                "volume_ml": volume if volume is not None and volume >= 0 else None,
            }
            entries = direct_watering if kind == "watering" else recent_events
            if len(entries) < RECENT_CARE_LIMIT:
                entries.append(record)
            if len(direct_watering) == len(recent_events) == RECENT_CARE_LIMIT:
                break
        care_status = "available" if care is not None else "unavailable"
        event_context = {
            "recent_care_records": {
                "status": care_status,
                "lookback_days": CALIBRATION_WINDOW.days,
                "events": recent_events,
            },
            "watering_history": {
                "lookback_days": CALIBRATION_WINDOW.days,
                "direct": {"status": care_status, "events": direct_watering},
                "inferred": _inferred_watering_records(inferred, history_start, now),
            },
        }
        if measurements is None:
            return {"status": "unavailable", **event_context}

        observations = []
        for row in measurements:
            measured_at = parse_record_time(row.get("measured_at"))
            weight_g = _number(row.get("weight_g"))
            if (
                measured_at is not None and since <= measured_at <= now
                and weight_g is not None and weight_g > 0
                and isinstance(row.get("device_id"), str) and row["device_id"]
            ):
                observations.append((measured_at, weight_g, row))
        if not observations:
            return {"status": "no_reading_in_last_24_hours", **event_context}

        measured_at, weight_g, latest = max(observations, key=lambda item: item[0])
        event_params = {
            "device_id": f"eq.{latest['device_id']}",
            "occurred_at": f"lte.{now.isoformat()}",
            "order": "occurred_at.desc,id.desc",
            "limit": "1",
        }

        async def read_weight_history(
            start: datetime, end: datetime, limit: str,
        ) -> list[dict] | None:
            bounds = f"(measured_at.gte.{start.isoformat()},measured_at.lte.{end.isoformat()})"
            return await read_rows(
                "weight_measurements",
                select=(
                    "calibration_id,measured_at,weight_g,temperature_c,humidity_percent,"
                    "light_ppfd,light_lux,soil_raw:raw_payload->>soil_raw,"
                    "light_raw:raw_payload->>light_raw"
                ),
                device_id=f"eq.{latest['device_id']}",
                source="eq.device",
                is_stable="eq.true",
                order="measured_at.desc,id.desc",
                limit=limit,
                **{"and": bounds},
            )

        is_fresh = now - measured_at <= FRESH_FOR
        faults, resets, watering, calibrations, history = await asyncio.gather(
            read_rows(
                "device_diagnostics",
                select="occurred_at",
                event_type=f"in.({','.join(INTERRUPTIONS)})",
                **event_params,
            ),
            read_rows(
                "device_diagnostics",
                select="occurred_at",
                event_type=f"in.({','.join(COLLECTION_RESETS)})",
                **event_params,
            ) if is_fresh else asyncio.sleep(0, result=None),
            read_rows(
                "device_diagnostics",
                select="occurred_at,details",
                event_type="eq.watering_suspected",
                **event_params,
            ),
            read_rows(
                "plant_water_calibrations",
                select="id,calibrated_at",
                is_active="eq.true",
                limit="1",
            ) if is_fresh else asyncio.sleep(0, result=None),
            read_weight_history(history_start, now, "1000")
            if is_fresh else asyncio.sleep(0, result=None),
        )

    age = now - measured_at
    fault_at = parse_record_time(faults[0].get("occurred_at")) if faults else None
    status = "recent" if age <= FRESH_FOR else "stale"
    if fault_at is not None and measured_at <= fault_at <= now:
        status = "interrupted"

    values = _sensor_values(latest)
    summary: dict[str, object] = {
        "status": status,
        "measured_at": measured_at.isoformat(),
        "age_minutes": round(age.total_seconds() / 60, 1),
        "weight_g": weight_g,
        **event_context,
        **{key: value for key, value in values.items() if value is not None},
    }
    watering_at = parse_record_time(watering[0].get("occurred_at")) if watering else None
    if watering and watering_at is not None and since <= watering_at <= now:
        details = watering[0].get("details")
        details = details if isinstance(details, dict) else {}
        summary["watering_suspected"] = {
            "occurred_at": watering_at.isoformat(),
            "age_minutes": round((now - watering_at).total_seconds() / 60, 1),
            "observed_weight_increase_g": _number(details.get("increase_g")),
            "within_30_minutes": now - watering_at < timedelta(minutes=30),
        }

    if status == "recent":
        calibration = calibrations[0] if calibrations else {}
        calibrated_at = parse_record_time(calibration.get("calibrated_at"))
        if latest.get("calibration_id") not in (None, calibration.get("id")):
            calibrated_at = None
        care_records = []
        setup_times = []
        for row in care or []:
            at = parse_record_time(row.get("occurred_at"))
            kind = row.get("event_type")
            if at is None or not (now - CALIBRATION_WINDOW <= at <= now):
                continue
            if row.get("device_id") not in (None, latest["device_id"]):
                continue
            if kind in ("setup_changed", "calibration"):
                setup_times.append(at)
            if kind in ("watering", "drainage"):
                volume = _number(row.get("volume_ml"))
                care_records.append(CareRecord(
                    at, kind, volume if volume is not None and volume >= 0 else None,
                ))
        if calibrated_at is not None:
            setup_times.append(calibrated_at)
        last_setup = max(setup_times, default=None)
        epoch = last_setup or history_start
        points = [WeightPoint(measured_at, weight_g, **values)]
        for row in history or []:
            at = parse_record_time(row.get("measured_at"))
            if at is None or at >= measured_at:
                continue
            if at < epoch or row.get("calibration_id") != latest.get("calibration_id"):
                break
            weight = _number(row.get("weight_g"))
            if weight is not None and weight > 0:
                points.append(WeightPoint(at, weight, **_sensor_values(row)))
        reset_at = parse_record_time(resets[0].get("occurred_at")) if resets else None
        assessment = assess_sensor_water(
            points,
            [record for record in care_records if record.at >= epoch],
            setup_at=last_setup,
            interrupted_at=reset_at,
            suspected_watering=(
                watering_at if watering_at is not None and epoch <= watering_at <= now else None
            ),
            diagnostics_available=all(
                rows is not None for rows in (faults, resets, watering, care, calibrations, history)
            ),
        )
        if last_setup is not None and last_setup >= measured_at:
            assessment = {"status": "awaiting_stable_weight"}
        summary["water_assessment"] = assessment
        if assessment["status"] == "diagnostics_unavailable":
            return summary

    await _save_sensor_assessment(base_url, headers, {
        "p_plant_id": plant_id,
        "p_device_id": latest["device_id"],
        "p_measured_at": measured_at.isoformat(),
        "p_evaluated_at": now.isoformat(),
        "p_observation_status": status,
        "p_summary": summary,
    })
    return summary
