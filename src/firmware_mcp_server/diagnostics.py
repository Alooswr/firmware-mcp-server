from __future__ import annotations

from typing import Any


BOOT_PATTERNS = (
    "boot",
    "booting",
    "startup",
    "system init",
    "app start",
    "ready",
)

CRASH_PATTERNS = (
    "panic",
    "hardfault",
    "hard fault",
    "assert",
    "exception",
    "segfault",
    "abort",
    "fatal",
    "core dump",
)

HANG_PATTERNS = (
    "hang",
    "stuck",
    "deadlock",
    "watchdog",
    "wdt",
    "timeout",
    "no response",
)


def serial_line_state(line: str) -> str:
    normalized = line.lower()

    if any(pattern in normalized for pattern in CRASH_PATTERNS):
        return "CRASH"
    if any(pattern in normalized for pattern in HANG_PATTERNS):
        return "HANG"
    if any(pattern in normalized for pattern in BOOT_PATTERNS):
        return "BOOT"

    return "UNKNOWN"


def tag_serial_event(
    event: dict[str, Any],
    recent_events: list[dict[str, Any]],
    reboot_window: int = 20,
    reboot_threshold: int = 3,
) -> dict[str, Any]:
    tagged = dict(event)
    state = serial_line_state(str(tagged.get("line", "")))

    if state == "BOOT":
        same_device_recent = [
            item
            for item in recent_events[-reboot_window:]
            if item.get("source") == "serial"
            and item.get("device_id") == tagged.get("device_id")
            and item.get("state") in {"BOOT", "REBOOT_LOOP"}
        ]
        if len(same_device_recent) + 1 >= reboot_threshold:
            state = "REBOOT_LOOP"

    tagged["state"] = state
    return tagged


def build_timeline(
    tool_traces: list[dict[str, Any]],
    serial_events: list[dict[str, Any]],
    device_id: str | None = None,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []

    for trace in tool_traces:
        if device_id is not None and trace.get("device_id") != device_id:
            continue
        timeline.append(
            {
                "timestamp": trace["start_time"],
                "source": "tool",
                "event": trace["event"],
                "tool_name": trace["tool_name"],
                "device_id": trace.get("device_id"),
                "start_time": trace["start_time"],
                "end_time": trace["end_time"],
                "status": trace["status"],
            }
        )

    for event in serial_events:
        if device_id is not None and event.get("device_id") != device_id:
            continue
        timeline.append(
            {
                "timestamp": event["timestamp"],
                "source": "serial",
                "event": event["event"],
                "device_id": event["device_id"],
                "state": event.get("state", "UNKNOWN"),
                "line": event["line"],
            }
        )

    return sorted(timeline, key=lambda item: item["timestamp"])


def classify_failure(timeline: list[dict[str, Any]]) -> dict[str, Any]:
    failed_tools = [
        item
        for item in timeline
        if item.get("source") == "tool" and item.get("status") == "fail"
    ]
    states = [item.get("state") for item in timeline if item.get("source") == "serial"]
    tool_names = [item.get("tool_name") for item in timeline if item.get("source") == "tool"]

    if any(item.get("tool_name") == "flash_firmware" for item in failed_tools):
        return failure_result("FLASH_FAILED", "flash_firmware failed")
    if any(item.get("tool_name") == "build_firmware" for item in failed_tools):
        return failure_result("BUILD_FAILED", "build_firmware failed")
    if any(item.get("tool_name") == "reset_device" for item in failed_tools):
        return failure_result("RESET_FAILED", "reset_device failed")
    if "REBOOT_LOOP" in states:
        return failure_result("REBOOT_LOOP", "repeated boot events detected")
    if "CRASH" in states and "flash_firmware" in tool_names:
        return failure_result("CRASH_AFTER_FLASH", "crash observed after flash activity")
    if "CRASH" in states:
        return failure_result("CRASH", "crash signature observed in serial logs")
    if "HANG" in states:
        return failure_result("HANG", "hang signature observed in serial logs")
    if "flash_firmware" in tool_names and "BOOT" not in states and "REBOOT_LOOP" not in states:
        return failure_result("NO_BOOT", "no boot signature observed after flash activity")

    return {
        "failure_type": "UNKNOWN",
        "message": "no deterministic failure rule matched",
    }


def failure_result(failure_type: str, message: str) -> dict[str, Any]:
    return {
        "failure_type": failure_type,
        "message": message,
    }
