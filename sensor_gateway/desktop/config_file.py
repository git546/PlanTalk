from __future__ import annotations

from pathlib import Path
import sys
from typing import Mapping

from ..config import GatewayConfig


CONFIG_FILENAME = ".env.gateway"


def application_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def config_path() -> Path:
    return application_dir() / CONFIG_FILENAME


def read_env(path: Path | None = None) -> dict[str, str]:
    target = path or config_path()
    values: dict[str, str] = {}
    if not target.exists():
        return values
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def update_env(updates: Mapping[str, str], path: Path | None = None) -> Path:
    target = path or config_path()
    current_lines = (
        target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    )
    remaining = dict(updates)
    output: list[str] = []
    for line in current_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)
    if not output:
        output.append("# PlanTalk sensor gateway local configuration")
    if remaining:
        if output and output[-1] != "":
            output.append("")
        for key, value in remaining.items():
            output.append(f"{key}={value}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    return target


def load_config() -> GatewayConfig:
    values = read_env()
    values.setdefault(
        "GATEWAY_DB_PATH",
        str(application_dir() / "data" / "gateway.sqlite3"),
    )
    return GatewayConfig.from_environment(values)


def safe_configuration_status() -> dict[str, bool]:
    config = load_config()
    return {
        "supabase": bool(config.supabase_url and config.supabase_publishable_key),
        "login": bool(config.supabase_email and config.supabase_password),
        "plant": bool(config.plant_id),
        "calibration": bool(
            config.raw_zero_value is not None
            and config.raw_grams_per_unit is not None
        ),
    }

