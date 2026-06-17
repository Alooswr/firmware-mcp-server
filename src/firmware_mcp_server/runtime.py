from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .config import CommandConfig, DeviceConfig, DeviceRegistry
from .diagnostics import build_timeline, classify_failure, tag_serial_event
from .errors import (
    CommandExecutionError,
    ToolError,
    UnknownToolError,
    ValidationError,
    failure,
    normalize_exception,
    success,
)
from .executor import run_command
from .logging_utils import get_stderr_logger
from .serial_reader import stream_serial_lines


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class DeviceRuntime:
    def __init__(self, registry: DeviceRegistry) -> None:
        self._registry = registry
        self._registry_lock = asyncio.Lock()
        self._locks: dict[str, asyncio.Lock] = {}

    async def reload(self) -> None:
        async with self._registry_lock:
            await asyncio.to_thread(self._registry.reload)

    async def reload_if_changed(self) -> bool:
        async with self._registry_lock:
            return await asyncio.to_thread(self._registry.reload_if_changed)

    async def get_device(self, device_id: str) -> DeviceConfig:
        async with self._registry_lock:
            return self._registry.get(device_id)

    def lock_for(self, device_id: str) -> asyncio.Lock:
        lock = self._locks.get(device_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[device_id] = lock
        return lock


class ToolExecutor:
    def __init__(self, runtime: DeviceRuntime) -> None:
        self._runtime = runtime
        self._logger = get_stderr_logger("firmware_mcp_server.runtime")
        self._stream_events: deque[dict[str, Any]] = deque(maxlen=1000)
        self._tool_traces: deque[dict[str, Any]] = deque(maxlen=1000)
        self._handlers: dict[str, ToolHandler] = {
            "build_firmware": self._build_firmware,
            "flash_firmware": self._flash_firmware,
            "read_serial_log": self._read_serial_log,
            "reset_device": self._reset_device,
        }

    async def execute(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        start_time = utc_now()
        device_id = trace_device_id(arguments)
        result: dict[str, Any]

        handler = self._handlers.get(name)
        if handler is None:
            result = failure(UnknownToolError(f"unknown tool: {name}").to_tool_error())
            self._emit_execution_trace(name, device_id, start_time, utc_now(), result)
            return result

        args = arguments or {}
        if not isinstance(args, dict):
            result = failure(ValidationError("tool arguments must be a JSON object").to_tool_error())
            self._emit_execution_trace(name, device_id, start_time, utc_now(), result)
            return result

        try:
            await self._runtime.reload_if_changed()
            result = await handler(args)
        except Exception as exc:
            result = failure(normalize_exception(exc))

        self._emit_execution_trace(name, device_id, start_time, utc_now(), result)
        return result

    async def _build_firmware(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self._run_device_command("build_firmware", args, lambda device: device.build)

    async def _flash_firmware(self, args: dict[str, Any]) -> dict[str, Any]:
        return await self._run_device_command("flash_firmware", args, lambda device: device.flash)

    async def _reset_device(self, args: dict[str, Any]) -> dict[str, Any]:
        def select_reset(device: DeviceConfig) -> CommandConfig:
            if device.reset is None:
                raise ValidationError(f"device has no reset.command configured: {device.device_id}")
            return device.reset

        return await self._run_device_command("reset_device", args, select_reset)

    async def _run_device_command(
        self,
        action: str,
        args: dict[str, Any],
        command_selector: Callable[[DeviceConfig], CommandConfig],
    ) -> dict[str, Any]:
        device_id = require_device_id(args)
        timeout_ms = optional_timeout_ms(args)

        async with self._runtime.lock_for(device_id):
            device = await self._runtime.get_device(device_id)
            command = command_selector(device)
            try:
                data = await execute_command_action(action, device_id, command, timeout_ms)
            except CommandExecutionError as exc:
                return failure(
                    ToolError(
                        error_type=command_failed_error_type(action),
                        message=exc.message,
                        recoverable=True,
                    )
                )

        if data["timed_out"]:
            return failure(
                ToolError(
                    error_type="TIMEOUT",
                    message=f"{action} timed out for device: {device_id}",
                    recoverable=True,
                ),
                data=data,
            )

        if data["exit_code"] != 0:
            return failure(
                ToolError(
                    error_type=command_failed_error_type(action),
                    message=f"{action} exited with code {data['exit_code']} for device: {device_id}",
                    recoverable=True,
                ),
                data=data,
            )

        return success(data)

    async def _read_serial_log(self, args: dict[str, Any]) -> dict[str, Any]:
        device_id = require_device_id(args)
        duration_ms = positive_int(args.get("duration_ms", 3000), "duration_ms")
        max_lines = positive_int(args.get("max_lines", 500), "max_lines")

        async with self._runtime.lock_for(device_id):
            device = await self._runtime.get_device(device_id)
            lines: list[dict[str, Any]] = []
            async for line in stream_serial_lines(device.serial, duration_ms, max_lines):
                lines.append(line)
                event = self._record_serial_stream_event(device_id, device.serial.port, line)
                self._emit_stream_event(event)

        return success(
            {
                "device_id": device_id,
                "action": "read_serial_log",
                "serial": {
                    "port": device.serial.port,
                    "baudrate": device.serial.baudrate,
                    "timeout_ms": device.serial.timeout_ms,
                },
                "duration_ms": duration_ms,
                "max_lines": max_lines,
                "line_count": len(lines),
                "lines": lines,
            }
        )

    def stream_events_snapshot(self) -> list[dict[str, Any]]:
        return list(self._stream_events)

    def tool_traces_snapshot(self) -> list[dict[str, Any]]:
        return list(self._tool_traces)

    def diagnostic_timeline(self, device_id: str | None = None) -> list[dict[str, Any]]:
        return build_timeline(
            self.tool_traces_snapshot(),
            self.stream_events_snapshot(),
            device_id=device_id,
        )

    def classify_diagnostics(self, device_id: str | None = None) -> dict[str, Any]:
        return classify_failure(self.diagnostic_timeline(device_id=device_id))

    def _record_serial_stream_event(
        self,
        device_id: str,
        port: str,
        line: dict[str, Any],
    ) -> dict[str, Any]:
        event = {
            "event": "serial_log_line",
            "source": "serial",
            "device_id": device_id,
            "port": port,
            "timestamp": line["timestamp"],
            "line": line["line"],
        }
        tagged_event = tag_serial_event(event, self.stream_events_snapshot())
        self._stream_events.append(tagged_event)
        return tagged_event

    def _emit_stream_event(self, event: dict[str, Any]) -> None:
        self._logger.info(
            json.dumps(
                event,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    def _emit_execution_trace(
        self,
        tool_name: str,
        device_id: str | None,
        start_time: str,
        end_time: str,
        result: dict[str, Any],
    ) -> None:
        trace = {
            "event": "tool_execution_trace",
            "tool_name": tool_name,
            "device_id": device_id,
            "start_time": start_time,
            "end_time": end_time,
            "status": "ok" if result.get("ok") is True else "fail",
        }
        self._tool_traces.append(trace)
        self._logger.info(
            json.dumps(
                trace,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )


async def execute_command_action(
    action: str,
    device_id: str,
    command: CommandConfig,
    timeout_ms: int | None,
) -> dict[str, Any]:
    try:
        result = await run_command(command, timeout_ms)
    except CommandExecutionError:
        raise

    return {
        "device_id": device_id,
        "action": action,
        **result,
    }


def require_device_id(args: dict[str, Any]) -> str:
    device_id = args.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValidationError("device_id must be a non-empty string")
    return device_id


def optional_timeout_ms(args: dict[str, Any]) -> int | None:
    value = args.get("timeout_ms")
    if value is None:
        return None
    return positive_int(value, "timeout_ms")


def positive_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{name} must be a positive integer")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def trace_device_id(arguments: dict[str, Any] | None) -> str | None:
    if not isinstance(arguments, dict):
        return None

    device_id = arguments.get("device_id")
    if isinstance(device_id, str) and device_id.strip():
        return device_id

    return None


def command_failed_error_type(action: str) -> str:
    if action == "build_firmware":
        return "BUILD_FAILED"
    if action == "flash_firmware":
        return "FLASH_FAILED"
    if action == "reset_device":
        return "RESET_FAILED"
    return "COMMAND_FAILED"
