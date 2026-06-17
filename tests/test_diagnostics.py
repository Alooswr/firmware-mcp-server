from __future__ import annotations

import unittest

from firmware_mcp_server.diagnostics import (
    build_timeline,
    classify_failure,
    serial_line_state,
    tag_serial_event,
)


class DiagnosticsTests(unittest.TestCase):
    def test_serial_line_state_mapping(self) -> None:
        self.assertEqual(serial_line_state("boot complete"), "BOOT")
        self.assertEqual(serial_line_state("panic: hardfault"), "CRASH")
        self.assertEqual(serial_line_state("watchdog timeout"), "HANG")
        self.assertEqual(serial_line_state("adc=1234"), "UNKNOWN")

    def test_reboot_loop_detection(self) -> None:
        recent = [
            {
                "source": "serial",
                "device_id": "dev",
                "state": "BOOT",
            },
            {
                "source": "serial",
                "device_id": "dev",
                "state": "BOOT",
            },
        ]
        event = tag_serial_event(
            {
                "event": "serial_log_line",
                "source": "serial",
                "device_id": "dev",
                "timestamp": "2026-06-17T00:00:02.000Z",
                "line": "booting",
            },
            recent,
        )

        self.assertEqual(event["state"], "REBOOT_LOOP")

    def test_build_timeline_orders_tool_and_serial_events(self) -> None:
        timeline = build_timeline(
            [
                {
                    "event": "tool_execution_trace",
                    "tool_name": "flash_firmware",
                    "device_id": "dev",
                    "start_time": "2026-06-17T00:00:02.000Z",
                    "end_time": "2026-06-17T00:00:03.000Z",
                    "status": "ok",
                }
            ],
            [
                {
                    "event": "serial_log_line",
                    "source": "serial",
                    "device_id": "dev",
                    "timestamp": "2026-06-17T00:00:01.000Z",
                    "state": "BOOT",
                    "line": "boot",
                }
            ],
        )

        self.assertEqual(timeline[0]["source"], "serial")
        self.assertEqual(timeline[1]["source"], "tool")

    def test_failure_classifier(self) -> None:
        result = classify_failure(
            [
                {
                    "source": "tool",
                    "tool_name": "flash_firmware",
                    "status": "fail",
                }
            ]
        )
        self.assertEqual(result["failure_type"], "FLASH_FAILED")

        result = classify_failure(
            [
                {
                    "source": "tool",
                    "tool_name": "flash_firmware",
                    "status": "ok",
                },
                {
                    "source": "serial",
                    "state": "CRASH",
                },
            ]
        )
        self.assertEqual(result["failure_type"], "CRASH_AFTER_FLASH")


if __name__ == "__main__":
    unittest.main()
