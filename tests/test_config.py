from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from firmware_mcp_server.config import DeviceRegistry


class DeviceRegistryTests(unittest.TestCase):
    def test_load_device_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "test-device",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
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

            registry = DeviceRegistry.load(str(config_path))
            device = registry.get("test-device")

            self.assertEqual(device.device_id, "test-device")
            self.assertEqual(device.build.command, ["python", "--version"])
            self.assertEqual(device.flash.command, ["python", "--version"])
            self.assertIsNone(device.reset)
            self.assertEqual(device.serial.port, "COM1")

    def test_reload_if_changed_only_reloads_after_file_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "devices.json"
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "device-a",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
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

            registry = DeviceRegistry.load(str(config_path))

            self.assertFalse(registry.reload_if_changed())

            time.sleep(0.01)
            config_path.write_text(
                json.dumps(
                    {
                        "devices": [
                            {
                                "device_id": "device-b",
                                "build": {
                                    "command": ["python", "--version"],
                                },
                                "flash": {
                                    "command": ["python", "--version"],
                                },
                                "serial": {
                                    "port": "COM2",
                                    "baudrate": 115200,
                                    "timeout_ms": 3000,
                                },
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(registry.reload_if_changed())
            self.assertEqual(registry.get("device-b").serial.port, "COM2")
            self.assertFalse(registry.reload_if_changed())


if __name__ == "__main__":
    unittest.main()
