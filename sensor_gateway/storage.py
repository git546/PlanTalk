from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Optional

from .models import (
    CareEvent,
    GatewayEvent,
    NormalizedMeasurement,
    RawSample,
    utc_now_iso,
)


@dataclass(frozen=True)
class OutboxItem:
    id: int
    kind: str
    dedupe_key: str
    payload: dict[str, Any]
    attempts: int


class GatewayStore:
    """Append raw data first, then keep uploadable records in a durable outbox."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma journal_mode = WAL")
        connection.execute("pragma foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                create table if not exists raw_samples (
                  id integer primary key autoincrement,
                  external_device_id text not null,
                  captured_at text not null,
                  source_sequence_no integer,
                  weight_g real,
                  raw_sensor_value real,
                  temperature_c real,
                  humidity_percent real,
                  light_lux real,
                  light_ppfd real,
                  raw_payload text not null,
                  created_at text not null
                );

                create index if not exists raw_samples_device_time_idx
                  on raw_samples(external_device_id, captured_at desc);

                create table if not exists normalized_measurements (
                  id integer primary key autoincrement,
                  external_device_id text not null,
                  sequence_no integer not null,
                  measured_at text not null,
                  weight_g real not null,
                  raw_sensor_value real,
                  sample_count integer not null,
                  is_stable integer not null,
                  temperature_c real,
                  humidity_percent real,
                  light_lux real,
                  light_ppfd real,
                  firmware_version text,
                  raw_payload text not null,
                  created_at text not null,
                  unique(external_device_id, sequence_no)
                );

                create table if not exists local_care_events (
                  id integer primary key autoincrement,
                  external_device_id text not null,
                  external_event_id text not null,
                  event_type text not null,
                  occurred_at text not null,
                  volume_ml real,
                  weight_g real,
                  notes text,
                  created_at text not null,
                  unique(external_device_id, external_event_id)
                );

                create table if not exists gateway_events (
                  id integer primary key autoincrement,
                  external_device_id text not null,
                  external_event_id text not null,
                  event_type text not null,
                  severity text not null,
                  occurred_at text not null,
                  details_json text not null,
                  created_at text not null,
                  unique(external_device_id, external_event_id)
                );

                create index if not exists gateway_events_device_time_idx
                  on gateway_events(external_device_id, occurred_at desc);

                create table if not exists outbox (
                  id integer primary key autoincrement,
                  kind text not null,
                  dedupe_key text not null unique,
                  payload_json text not null,
                  status text not null default 'pending',
                  attempts integer not null default 0,
                  next_attempt_at text not null,
                  last_error text,
                  created_at text not null,
                  sent_at text
                );

                create index if not exists outbox_pending_idx
                  on outbox(status, next_attempt_at, id);

                create table if not exists metadata (
                  key text primary key,
                  value text not null
                );
                """
            )

    def append_raw(self, external_device_id: str, sample: RawSample) -> int:
        sample.validate()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                insert into raw_samples (
                  external_device_id, captured_at, source_sequence_no,
                  weight_g, raw_sensor_value, temperature_c,
                  humidity_percent, light_lux, light_ppfd,
                  raw_payload, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_device_id,
                    sample.captured_at,
                    sample.sequence_no,
                    sample.weight_g,
                    sample.raw_sensor_value,
                    sample.temperature_c,
                    sample.humidity_percent,
                    sample.light_lux,
                    sample.light_ppfd,
                    json.dumps(sample.raw_payload, ensure_ascii=False),
                    utc_now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def next_sequence(self, external_device_id: str) -> int:
        key = f"next_sequence:{external_device_id}"
        with self.connect() as connection:
            row = connection.execute(
                "select value from metadata where key = ?",
                (key,),
            ).fetchone()
            sequence = int(row["value"]) if row else 1
            connection.execute(
                """
                insert into metadata(key, value) values (?, ?)
                on conflict(key) do update set value = excluded.value
                """,
                (key, str(sequence + 1)),
            )
            return sequence

    def get_metadata(self, key: str) -> Optional[str]:
        with self.connect() as connection:
            row = connection.execute(
                "select value from metadata where key = ?",
                (key,),
            ).fetchone()
        return str(row["value"]) if row else None

    def set_metadata(self, key: str, value: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                insert into metadata(key, value) values (?, ?)
                on conflict(key) do update set value = excluded.value
                """,
                (key, value),
            )

    def enqueue_measurement(
        self,
        external_device_id: str,
        measurement: NormalizedMeasurement,
    ) -> bool:
        now = utc_now_iso()
        payload = measurement.to_dict()
        dedupe_key = f"measurement:{external_device_id}:{measurement.sequence_no}"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                insert or ignore into normalized_measurements (
                  external_device_id, sequence_no, measured_at, weight_g,
                  raw_sensor_value, sample_count, is_stable,
                  temperature_c, humidity_percent, light_lux, light_ppfd,
                  firmware_version, raw_payload, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_device_id,
                    measurement.sequence_no,
                    measurement.measured_at,
                    measurement.weight_g,
                    measurement.raw_sensor_value,
                    measurement.sample_count,
                    int(measurement.is_stable),
                    measurement.temperature_c,
                    measurement.humidity_percent,
                    measurement.light_lux,
                    measurement.light_ppfd,
                    measurement.firmware_version,
                    json.dumps(measurement.raw_payload, ensure_ascii=False),
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                insert or ignore into outbox (
                  kind, dedupe_key, payload_json, next_attempt_at, created_at
                ) values ('measurement', ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return True

    def enqueue_care_event(
        self,
        external_device_id: str,
        event: CareEvent,
    ) -> bool:
        event.validate()
        now = utc_now_iso()
        dedupe_key = f"event:{external_device_id}:{event.external_event_id}"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                insert or ignore into local_care_events (
                  external_device_id, external_event_id, event_type,
                  occurred_at, volume_ml, weight_g, notes, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_device_id,
                    event.external_event_id,
                    event.event_type,
                    event.occurred_at,
                    event.volume_ml,
                    event.weight_g,
                    event.notes,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                insert or ignore into outbox (
                  kind, dedupe_key, payload_json, next_attempt_at, created_at
                ) values ('care_event', ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    json.dumps(event.to_dict(), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return True

    def enqueue_gateway_event(
        self,
        external_device_id: str,
        event: GatewayEvent,
    ) -> bool:
        event.validate()
        now = utc_now_iso()
        dedupe_key = f"gateway_event:{external_device_id}:{event.external_event_id}"
        with self.connect() as connection:
            cursor = connection.execute(
                """
                insert or ignore into gateway_events (
                  external_device_id, external_event_id, event_type,
                  severity, occurred_at, details_json, created_at
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    external_device_id,
                    event.external_event_id,
                    event.event_type,
                    event.severity,
                    event.occurred_at,
                    json.dumps(event.details, ensure_ascii=False),
                    now,
                ),
            )
            if cursor.rowcount == 0:
                return False
            connection.execute(
                """
                insert or ignore into outbox (
                  kind, dedupe_key, payload_json, next_attempt_at, created_at
                ) values ('gateway_event', ?, ?, ?, ?)
                """,
                (
                    dedupe_key,
                    json.dumps(event.to_dict(), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return True

    def pending(self, limit: int = 50) -> list[OutboxItem]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                select id, kind, dedupe_key, payload_json, attempts
                from outbox
                where status in ('pending', 'failed')
                  and next_attempt_at <= ?
                order by case when kind = 'gateway_event' then 1 else 0 end, id
                limit ?
                """,
                (utc_now_iso(), limit),
            ).fetchall()
        return [
            OutboxItem(
                id=int(row["id"]),
                kind=str(row["kind"]),
                dedupe_key=str(row["dedupe_key"]),
                payload=json.loads(row["payload_json"]),
                attempts=int(row["attempts"]),
            )
            for row in rows
        ]

    def mark_sent(self, item_id: int) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                update outbox
                set status = 'sent', sent_at = ?, last_error = null
                where id = ?
                """,
                (utc_now_iso(), item_id),
            )

    def mark_failed(self, item_id: int, attempts: int, error: str) -> None:
        delay_seconds = min(15 * (2 ** min(attempts, 8)), 3600)
        next_attempt = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        with self.connect() as connection:
            connection.execute(
                """
                update outbox
                set status = 'failed', attempts = ?, last_error = ?,
                    next_attempt_at = ?
                where id = ?
                """,
                (
                    attempts,
                    error[:1000],
                    next_attempt.isoformat(timespec="milliseconds"),
                    item_id,
                ),
            )

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            raw_count = connection.execute(
                "select count(*) from raw_samples"
            ).fetchone()[0]
            measurement_count = connection.execute(
                "select count(*) from normalized_measurements"
            ).fetchone()[0]
            event_count = connection.execute(
                "select count(*) from local_care_events"
            ).fetchone()[0]
            gateway_event_count = connection.execute(
                "select count(*) from gateway_events"
            ).fetchone()[0]
            pending_count = connection.execute(
                "select count(*) from outbox where status in ('pending', 'failed')"
            ).fetchone()[0]
            sent_count = connection.execute(
                "select count(*) from outbox where status = 'sent'"
            ).fetchone()[0]
        return {
            "raw_samples": int(raw_count),
            "normalized_measurements": int(measurement_count),
            "care_events": int(event_count),
            "gateway_events": int(gateway_event_count),
            "outbox_pending": int(pending_count),
            "outbox_sent": int(sent_count),
        }

    def recent_gateway_events(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit < 1:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                """
                select event_type, severity, occurred_at, details_json
                from gateway_events
                order by occurred_at desc, id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "event_type": str(row["event_type"]),
                "severity": str(row["severity"]),
                "occurred_at": str(row["occurred_at"]),
                "details": json.loads(row["details_json"]),
            }
            for row in rows
        ]

    def export_jsonl(self, output_path: Path) -> int:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            rows = connection.execute(
                """
                select external_device_id, sequence_no, measured_at, weight_g,
                       raw_sensor_value, sample_count, is_stable,
                       temperature_c, humidity_percent, light_lux, light_ppfd,
                       firmware_version, raw_payload
                from normalized_measurements
                order by measured_at, id
                """
            ).fetchall()
        with output_path.open("w", encoding="utf-8") as stream:
            for row in rows:
                payload = dict(row)
                payload["is_stable"] = bool(payload["is_stable"])
                payload["raw_payload"] = json.loads(payload["raw_payload"])
                stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return len(rows)

