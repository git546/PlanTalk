from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from typing import Optional, TextIO
from uuid import uuid4

from .adapters import (
    JsonLinesAdapter,
    SerialJsonLinesAdapter,
    SimulatorAdapter,
    list_serial_ports,
)
from .config import GatewayConfig, load_env_file
from .models import CareEvent, normalize_timestamp
from .service import GatewayService
from .storage import GatewayStore
from .supabase_client import SupabaseGatewayClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plantalk-sensor-gateway",
        description="센서 스펙과 분리된 PlanTalk 측정 수집 게이트웨이",
    )
    parser.add_argument(
        "--env-file",
        default="sensor_gateway/.env.gateway",
        help="게이트웨이 설정 파일 경로",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="로컬 SQLite 저장소 초기화")
    subparsers.add_parser("status", help="로컬 저장·전송 큐 현황 표시")
    subparsers.add_parser("ports", help="현재 PC의 시리얼 포트 목록 표시")

    run = subparsers.add_parser("run", help="센서 입력 수집")
    run.add_argument(
        "--adapter",
        choices=("stdin", "file", "serial", "simulator"),
        default="simulator",
    )
    run.add_argument("--input", help="file 어댑터의 JSONL 경로")
    run.add_argument("--port", help="serial 어댑터 COM 포트(예: COM3)")
    run.add_argument("--baud", type=int, help="serial 통신속도")
    run.add_argument("--serial-timeout", type=float, help="serial 읽기 timeout(초)")
    run.add_argument(
        "--no-reconnect",
        action="store_true",
        help="serial 연결이 끊어지면 재연결하지 않고 종료",
    )
    run.add_argument(
        "--trust-device-sequence",
        action="store_true",
        help="재부팅 후에도 유지되는 기기 순번일 때만 사용",
    )
    run.add_argument(
        "--max-samples",
        type=int,
        default=0,
        help="serial 수집 개수 제한, 0이면 Ctrl+C까지 계속",
    )
    run.add_argument("--upload", action="store_true", help="Supabase 전송 활성화")
    run.add_argument("--count", type=int, default=120)
    run.add_argument("--interval", type=float, default=1.0)
    run.add_argument("--start-weight", type=float, default=3800.0)
    run.add_argument("--daily-loss", type=float, default=80.0)
    run.add_argument("--noise", type=float, default=0.6)
    run.add_argument("--realtime", action="store_true", help="시뮬레이터 실제 시간 대기")

    flush = subparsers.add_parser("flush", help="미전송 큐를 Supabase로 재전송")
    flush.add_argument("--limit", type=int, help="현재 설정 대신 배치 크기 지정")

    event = subparsers.add_parser("event", help="급수·배수 등 돌봄 이벤트 기록")
    event.add_argument(
        "event_type",
        choices=("watering", "drainage", "calibration", "setup_changed"),
    )
    event.add_argument("--volume", type=float)
    event.add_argument("--weight", type=float)
    event.add_argument("--notes")
    event.add_argument("--event-id")
    event.add_argument("--occurred-at")
    event.add_argument("--upload", action="store_true")

    export = subparsers.add_parser("export", help="정규화 측정값을 JSONL로 내보내기")
    export.add_argument(
        "--output",
        default="sensor_gateway/exports/measurements.jsonl",
    )

    subparsers.add_parser("contract", help="센서 어댑터 표준 JSON 예시 표시")

    calibration = subparsers.add_parser(
        "calibration",
        help="영점·기준 추 원본값으로 로드셀 환산계수 계산",
    )
    calibration.add_argument("--zero-raw", type=float, required=True)
    calibration.add_argument("--loaded-raw", type=float, required=True)
    calibration.add_argument("--known-weight", type=float, required=True)
    return parser


def load_config(path: str) -> GatewayConfig:
    load_env_file(Path(path))
    config = GatewayConfig.from_environment()
    config.validate_local()
    return config


def create_service(
    config: GatewayConfig,
    *,
    remote: bool,
) -> GatewayService:
    store = GatewayStore(config.db_path)
    uploader = SupabaseGatewayClient(config) if remote else None
    return GatewayService(config, store, uploader)


def _open_adapter(
    args: argparse.Namespace,
    config: GatewayConfig,
    event_callback=None,
) -> tuple[object, Optional[TextIO]]:
    if args.adapter == "stdin":
        return JsonLinesAdapter(sys.stdin, config.mapping), None
    if args.adapter == "file":
        if not args.input:
            raise ValueError("--adapter file에는 --input 경로가 필요합니다.")
        stream = Path(args.input).open("r", encoding="utf-8")
        return JsonLinesAdapter(stream, config.mapping), stream
    if args.adapter == "serial":
        reconnect_seconds = (
            0 if args.no_reconnect else config.serial_reconnect_seconds
        )
        return (
            SerialJsonLinesAdapter(
                port=args.port or config.serial_port,
                baud=args.baud or config.serial_baud,
                timeout_seconds=(
                    args.serial_timeout or config.serial_timeout_seconds
                ),
                reconnect_seconds=reconnect_seconds,
                mapping=config.mapping,
                trust_device_sequence=args.trust_device_sequence,
                max_samples=args.max_samples,
                event_callback=event_callback,
            ),
            None,
        )
    return (
        SimulatorAdapter(
            count=args.count,
            interval_seconds=args.interval,
            start_weight_g=args.start_weight,
            daily_loss_g=args.daily_loss,
            noise_g=args.noise,
            sleep=args.realtime,
        ),
        None,
    )


def contract_example() -> dict[str, object]:
    return {
        "status": "ok",
        "hx711_ready": True,
        "raw_sensor_value": 788240,
        "sequence_no": 1532,
        "device_uptime_ms": 3064000,
        "temperature_c": 24.3,
        "humidity_percent": 56.1,
        "soil_raw": 491,
        "light_raw": 720,
    }


def calculate_calibration(
    *,
    zero_raw: float,
    loaded_raw: float,
    known_weight_g: float,
) -> dict[str, float]:
    if known_weight_g <= 0:
        raise ValueError("--known-weight는 0보다 커야 합니다.")
    raw_delta = loaded_raw - zero_raw
    if raw_delta == 0:
        raise ValueError("영점과 기준 추의 원본값이 같아 환산할 수 없습니다.")
    return {
        "zero_raw": zero_raw,
        "loaded_raw": loaded_raw,
        "known_weight_g": known_weight_g,
        "raw_delta": raw_delta,
        "grams_per_unit": known_weight_g / raw_delta,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.env_file)
        if args.command == "contract":
            print(json.dumps(contract_example(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "ports":
            ports = [port.to_dict() for port in list_serial_ports()]
            print(json.dumps({"ports": ports}, ensure_ascii=False, indent=2))
            return 0 if ports else 2
        if args.command == "calibration":
            result = calculate_calibration(
                zero_raw=args.zero_raw,
                loaded_raw=args.loaded_raw,
                known_weight_g=args.known_weight,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"GATEWAY_RAW_ZERO_VALUE={result['zero_raw']:.10g}")
            print(
                "GATEWAY_RAW_GRAMS_PER_UNIT="
                f"{result['grams_per_unit']:.12g}"
            )
            return 0

        store = GatewayStore(config.db_path)
        if args.command == "init":
            print(f"SQLite 저장소 준비 완료: {config.db_path}")
            return 0
        if args.command == "status":
            print(
                json.dumps(
                    {
                        "config": config.safe_summary(),
                        "storage": store.stats(),
                        "recent_gateway_events": store.recent_gateway_events(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if args.command == "export":
            output = Path(args.output)
            count = store.export_jsonl(output)
            print(f"{count}개 측정값을 내보냈습니다: {output}")
            return 0

        remote = bool(getattr(args, "upload", False) or args.command == "flush")
        if remote:
            config.validate_remote()
        service = create_service(config, remote=remote)

        if args.command == "run":
            adapter, opened_stream = _open_adapter(
                args,
                config,
                event_callback=service.record_transport_event,
            )
            try:
                summary = service.run(adapter, upload=args.upload)  # type: ignore[arg-type]
            finally:
                if opened_stream is not None:
                    opened_stream.close()
            print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
            return 0
        if args.command == "flush":
            if args.limit is not None:
                if args.limit < 1:
                    raise ValueError("--limit은 1 이상이어야 합니다.")
                config = replace(config, upload_batch_size=args.limit)
                service = create_service(config, remote=True)
            sent, failed = service.flush_outbox()
            print(json.dumps({"sent": sent, "failed": failed}, indent=2))
            return 0 if failed == 0 else 2
        if args.command == "event":
            event = CareEvent(
                event_type=args.event_type,
                occurred_at=normalize_timestamp(args.occurred_at),
                external_event_id=(
                    args.event_id
                    or f"{config.external_device_id}-{args.event_type}-{uuid4().hex}"
                ),
                volume_ml=args.volume,
                weight_g=args.weight,
                notes=args.notes,
            )
            created = service.record_event(event, upload=args.upload)
            print("이벤트 저장 완료" if created else "이미 저장된 이벤트입니다.")
            return 0
    except KeyboardInterrupt:
        print("\n사용자가 수집을 중지했습니다.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    parser.error("지원하지 않는 명령입니다.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

