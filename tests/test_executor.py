from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from firmware_mcp_server.config import CommandConfig, DeviceRegistry
from firmware_mcp_server.executor import run_command
from firmware_mcp_server.runtime import DeviceRuntime, ToolExecutor


class ExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_command_success(self) -> None:
        result = await run_command(
            CommandConfig(
                command=[
                    sys.executable,
                    "-c",
                    "print('ok')",
                ]
            ),
            timeout_ms=5000,
        )

        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertEqual(result["stdout"].strip(), "ok")
        self.assertEqual(result["stderr"], "")

    async def test_tool_executor_wraps_command_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": [sys.executable, "-c", "print('built')"],
                                },
                                "flash": {
                                    "command": [sys.executable, "-c", "print('flashed')"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            executor = ToolExecutor(DeviceRuntime(DeviceRegistry.load(str(config_path))))
            result = await executor.execute("build_firmware", {"device_id": "test-device"})

            self.assertTrue(result["ok"])
            self.assertIsNone(result["error"])
            self.assertEqual(result["data"]["action"], "build_firmware")
            self.assertEqual(result["data"]["stdout"].strip(), "built")

    async def test_tool_executor_wraps_unknown_tool_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": [sys.executable, "--version"],
                                },
                                "flash": {
                                    "command": [sys.executable, "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            executor = ToolExecutor(DeviceRuntime(DeviceRegistry.load(str(config_path))))
            result = await executor.execute("missing_tool", {})

            self.assertFalse(result["ok"])
            self.assertIsNone(result["data"])
            self.assertEqual(result["error"]["error_type"], "UNKNOWN_TOOL")
            self.assertTrue(result["error"]["recoverable"])

    async def test_tool_executor_categorizes_build_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": [sys.executable, "-c", "import sys; sys.exit(7)"],
                                },
                                "flash": {
                                    "command": [sys.executable, "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            executor = ToolExecutor(DeviceRuntime(DeviceRegistry.load(str(config_path))))
            result = await executor.execute("build_firmware", {"device_id": "test-device"})

            self.assertFalse(result["ok"])
            self.assertEqual(result["data"]["exit_code"], 7)
            self.assertEqual(result["error"]["error_type"], "BUILD_FAILED")
            self.assertTrue(result["error"]["recoverable"])

    async def test_tool_executor_records_structured_serial_stream_event(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": [sys.executable, "--version"],
                                },
                                "flash": {
                                    "command": [sys.executable, "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            executor = ToolExecutor(DeviceRuntime(DeviceRegistry.load(str(config_path))))
            event = executor._record_serial_stream_event(
                "test-device",
                "COM1",
                {
                    "timestamp": "2026-06-17T00:00:00.000Z",
                    "line": "ready",
                },
            )

            self.assertEqual(event["device_id"], "test-device")
            self.assertEqual(event["timestamp"], "2026-06-17T00:00:00.000Z")
            self.assertEqual(event["source"], "serial")
            self.assertEqual(event["state"], "BOOT")
            self.assertEqual(executor.stream_events_snapshot(), [event])

    async def test_tool_executor_builds_internal_diagnostic_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": [sys.executable, "--version"],
                                },
                                "flash": {
                                    "command": [sys.executable, "--version"],
                                },
                                "serial": {
                                    "port": "COM1",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            executor = ToolExecutor(DeviceRuntime(DeviceRegistry.load(str(config_path))))
            executor._record_serial_stream_event(
                "test-device",
                "COM1",
                {
                    "timestamp": "2026-06-17T00:00:00.000Z",
                    "line": "panic: hardfault",
                },
            )
            await executor.execute("flash_firmware", {"device_id": "test-device"})

            timeline = executor.diagnostic_timeline("test-device")
            classification = executor.classify_diagnostics("test-device")

            self.assertEqual(timeline[0]["source"], "serial")
            self.assertEqual(timeline[0]["state"], "CRASH")
            self.assertEqual(classification["failure_type"], "CRASH_AFTER_FLASH")


if __name__ == "__main__":
    unittest.main()
