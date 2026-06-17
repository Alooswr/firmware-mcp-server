from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ConfigLoadError, DeviceNotFoundError


class DeviceConfigError(ConfigLoadError):
    pass


@dataclass(frozen=True)
class CommandConfig:
    command: list[str]
    cwd: str | None = None


@dataclass(frozen=True)
class SerialConfig:
    port: str
    baudrate: int
    timeout_ms: int


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str
    build: CommandConfig
    flash: CommandConfig
    reset: CommandConfig | None
    serial: SerialConfig


@dataclass(frozen=True)
class ConfigFingerprint:
    mtime_ns: int
    size: int


class DeviceRegistry:
    def __init__(
        self,
        config_path: Path,
        devices: dict[str, DeviceConfig],
        fingerprint: ConfigFingerprint,
    ) -> None:
        self._config_path = config_path
        self._devices = devices
        self._fingerprint = fingerprint

    @classmethod
    def load(cls, config_path: str | None = None) -> "DeviceRegistry":
        path = resolve_config_path(config_path)
        devices = load_devices_from_path(path)
        fingerprint = get_config_fingerprint(path)
        return cls(path, devices, fingerprint)

    def reload(self) -> None:
        self._devices = load_devices_from_path(self._config_path)
        self._fingerprint = get_config_fingerprint(self._config_path)

    def reload_if_changed(self, debounce_seconds: float = 0.05) -> bool:
        current = get_config_fingerprint(self._config_path)
        if current == self._fingerprint:
            return False

        current = get_stable_config_fingerprint(self._config_path, debounce_seconds, current)
        if current == self._fingerprint:
            return False

        self._devices = load_devices_from_path(self._config_path)
        self._fingerprint = current
        return True

    def get(self, device_id: str) -> DeviceConfig:
        device = self._devices.get(device_id)
        if device is None:
            available = ", ".join(sorted(self._devices))
            raise DeviceNotFoundError(f"unknown device_id: {device_id}; available devices: {available}")
        return device

    def list_ids(self) -> list[str]:
        return sorted(self._devices)


def get_config_fingerprint(path: Path) -> ConfigFingerprint:
    try:
        stat = path.stat()
    except OSError as exc:
        raise DeviceConfigError(f"failed to stat device config: {path}") from exc

    return ConfigFingerprint(
        mtime_ns=stat.st_mtime_ns,
        size=stat.st_size,
    )


def get_stable_config_fingerprint(
    path: Path,
    debounce_seconds: float,
    initial: ConfigFingerprint | None = None,
    attempts: int = 3,
) -> ConfigFingerprint:
    previous = initial or get_config_fingerprint(path)

    for _ in range(max(1, attempts)):
        if debounce_seconds > 0:
            time.sleep(debounce_seconds)

        current = get_config_fingerprint(path)
        if current == previous:
            return current
        previous = current

    return previous


def load_devices_from_path(path: Path) -> dict[str, DeviceConfig]:
    try:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except OSError as exc:
        raise DeviceConfigError(f"failed to read device config: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DeviceConfigError(f"invalid device config JSON: {path}") from exc

    devices_raw = raw.get("devices")
    if not isinstance(devices_raw, list) or not devices_raw:
        raise DeviceConfigError("config/devices.json must contain a non-empty devices array")

    devices: dict[str, DeviceConfig] = {}
    for entry in devices_raw:
        device = parse_device(entry)
        if device.device_id in devices:
            raise DeviceConfigError(f"duplicate device_id: {device.device_id}")
        devices[device.device_id] = device

    return devices


def resolve_config_path(config_path: str | None) -> Path:
    if config_path:
        path = Path(config_path)
    elif os.environ.get("FIRMWARE_MCP_DEVICES_CONFIG"):
        path = Path(os.environ["FIRMWARE_MCP_DEVICES_CONFIG"])
    else:
        path = Path.cwd() / "config" / "devices.json"

    if not path.exists():
        raise DeviceConfigError(f"device config file does not exist: {path}")

    return path


def parse_device(raw: Any) -> DeviceConfig:
    if not isinstance(raw, dict):
        raise DeviceConfigError("each device entry must be a JSON object")

    device_id = raw.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise DeviceConfigError("device_id must be a non-empty string")

    return DeviceConfig(
        device_id=device_id,
        build=parse_command(raw.get("build"), f"{device_id}.build", required=True),
        flash=parse_command(raw.get("flash"), f"{device_id}.flash", required=True),
        reset=parse_command(raw.get("reset"), f"{device_id}.reset", required=False),
        serial=parse_serial(raw.get("serial"), device_id),
    )


def parse_command(raw: Any, name: str, required: bool) -> CommandConfig | None:
    if raw is None:
        if required:
            raise DeviceConfigError(f"{name} is required")
        return None

    if not isinstance(raw, dict):
        raise DeviceConfigError(f"{name} must be a JSON object")

    command = raw.get("command")
    if not isinstance(command, list) or not command:
        raise DeviceConfigError(f"{name}.command must be a non-empty string array")

    for index, arg in enumerate(command):
        if not isinstance(arg, str) or not arg:
            raise DeviceConfigError(f"{name}.command[{index}] must be a non-empty string")

    cwd = raw.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd.strip()):
        raise DeviceConfigError(f"{name}.cwd must be a non-empty string when provided")

    return CommandConfig(command=command, cwd=cwd)


def parse_serial(raw: Any, device_id: str) -> SerialConfig:
    if not isinstance(raw, dict):
        raise DeviceConfigError(f"{device_id}.serial is required and must be a JSON object")

    port = raw.get("port")
    baudrate = raw.get("baudrate")
    timeout_ms = raw.get("timeout_ms")

    if not isinstance(port, str) or not port.strip():
        raise DeviceConfigError(f"{device_id}.serial.port must be a non-empty string")
    if not isinstance(baudrate, int) or baudrate <= 0:
        raise DeviceConfigError(f"{device_id}.serial.baudrate must be a positive integer")
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        raise DeviceConfigError(f"{device_id}.serial.timeout_ms must be a positive integer")

    return SerialConfig(port=port, baudrate=baudrate, timeout_ms=timeout_ms)
