from __future__ import annotations

import json
import time
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import GatewayConfig
from .models import CareEvent, GatewayEvent, NormalizedMeasurement


class GatewayHttpError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"Supabase 요청 실패({status}): {message[:500]}")


class SupabaseGatewayClient:
    """Small REST/Auth client using only a publishable key and a user session."""

    def __init__(self, config: GatewayConfig, timeout_seconds: float = 15.0) -> None:
        config.validate_remote()
        self.config = config
        self.timeout_seconds = timeout_seconds
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.expires_at = 0.0
        self.user_id: Optional[str] = None
        self.device_database_id: Optional[str] = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        query: Optional[dict[str, str]] = None,
        authenticated: bool = False,
        prefer: Optional[str] = None,
    ) -> Any:
        url = f"{self.config.supabase_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "apikey": self.config.supabase_publishable_key,
            "Content-Type": "application/json; charset=utf-8",
        }
        if authenticated:
            self.ensure_session()
            headers["Authorization"] = f"Bearer {self.access_token}"
        if prefer:
            headers["Prefer"] = prefer
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = exc.reason or "HTTP error"
            raise GatewayHttpError(exc.code, body) from exc
        except URLError as exc:
            raise RuntimeError(f"Supabase 네트워크 연결 실패: {exc.reason}") from exc

    def login(self) -> None:
        response = self._request(
            "POST",
            "/auth/v1/token",
            query={"grant_type": "password"},
            payload={
                "email": self.config.supabase_email,
                "password": self.config.supabase_password,
            },
        )
        self._save_session(response)

    def refresh(self) -> None:
        if not self.refresh_token:
            self.login()
            return
        response = self._request(
            "POST",
            "/auth/v1/token",
            query={"grant_type": "refresh_token"},
            payload={"refresh_token": self.refresh_token},
        )
        self._save_session(response)

    def _save_session(self, response: dict[str, Any]) -> None:
        access_token = response.get("access_token")
        refresh_token = response.get("refresh_token")
        user = response.get("user") or {}
        user_id = user.get("id")
        if not access_token or not refresh_token or not user_id:
            raise RuntimeError("Supabase 로그인 응답에 세션 정보가 없습니다.")
        self.access_token = str(access_token)
        self.refresh_token = str(refresh_token)
        self.user_id = str(user_id)
        self.expires_at = time.time() + float(response.get("expires_in", 3600))

    def ensure_session(self) -> None:
        if not self.access_token:
            self.login()
        elif time.time() >= self.expires_at - 60:
            self.refresh()

    def ensure_device(self) -> str:
        if self.device_database_id:
            return self.device_database_id
        self.ensure_session()
        assert self.user_id is not None
        rows = self._request(
            "GET",
            "/rest/v1/measurement_devices",
            query={
                "select": "id,external_device_id",
                "user_id": f"eq.{self.user_id}",
                "external_device_id": f"eq.{self.config.external_device_id}",
                "limit": "1",
            },
            authenticated=True,
        )
        if rows:
            self.device_database_id = str(rows[0]["id"])
            return self.device_database_id

        try:
            inserted = self._request(
                "POST",
                "/rest/v1/measurement_devices",
                query={"select": "id,external_device_id"},
                payload={
                    "user_id": self.user_id,
                    "external_device_id": self.config.external_device_id,
                    "name": self.config.device_name,
                    "hardware_model": self.config.hardware_model,
                    "firmware_version": self.config.firmware_version,
                    "last_seen_at": None,
                },
                authenticated=True,
                prefer="return=representation",
            )
        except GatewayHttpError as exc:
            if exc.status != 409:
                raise
            return self.ensure_device()
        if not inserted:
            raise RuntimeError("측정 기기를 등록하지 못했습니다.")
        self.device_database_id = str(inserted[0]["id"])
        return self.device_database_id

    def upload_measurement(self, measurement: NormalizedMeasurement) -> None:
        device_id = self.ensure_device()
        payload = {
            "plant_id": self.config.plant_id,
            "device_id": device_id,
            "source": "device",
            "weight_g": measurement.weight_g,
            "raw_sensor_value": measurement.raw_sensor_value,
            "sequence_no": measurement.sequence_no,
            "is_stable": measurement.is_stable,
            "sample_count": measurement.sample_count,
            "firmware_version": measurement.firmware_version,
            "temperature_c": measurement.temperature_c,
            "humidity_percent": measurement.humidity_percent,
            "light_lux": measurement.light_lux,
            "light_ppfd": measurement.light_ppfd,
            "measured_at": measurement.measured_at,
            "raw_payload": measurement.raw_payload,
        }
        try:
            self._request(
                "POST",
                "/rest/v1/weight_measurements",
                payload=payload,
                authenticated=True,
                prefer="return=minimal",
            )
        except GatewayHttpError as exc:
            if exc.status != 409:
                raise

    def upload_care_event(self, event: CareEvent) -> None:
        device_id = self.ensure_device()
        payload = {
            "plant_id": self.config.plant_id,
            "device_id": device_id,
            "event_type": event.event_type,
            "source": "device",
            "volume_ml": event.volume_ml,
            "weight_g": event.weight_g,
            "external_event_id": event.external_event_id,
            "occurred_at": event.occurred_at,
            "notes": event.notes,
            "raw_payload": {},
        }
        try:
            self._request(
                "POST",
                "/rest/v1/care_events",
                payload=payload,
                authenticated=True,
                prefer="return=minimal",
            )
        except GatewayHttpError as exc:
            if exc.status != 409:
                raise

    def upload_gateway_event(self, event: GatewayEvent) -> None:
        device_id = self.ensure_device()
        payload = {
            "device_id": device_id,
            "plant_id": self.config.plant_id,
            "external_event_id": event.external_event_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "occurred_at": event.occurred_at,
            "details": event.details,
        }
        try:
            self._request(
                "POST",
                "/rest/v1/device_diagnostics",
                payload=payload,
                authenticated=True,
                prefer="return=minimal",
            )
        except GatewayHttpError as exc:
            if exc.status != 409:
                raise

