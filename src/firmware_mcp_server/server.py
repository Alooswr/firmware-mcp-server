from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import DeviceRegistry
from .runtime import DeviceRuntime, ToolExecutor


server = Server("firmware-automation-mcp")
runtime = DeviceRuntime(DeviceRegistry.load())
executor = ToolExecutor(runtime)


DEVICE_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "device_id": {
            "type": "string",
        },
        "timeout_ms": {
            "type": "integer",
            "minimum": 1,
        },
    },
    "required": ["device_id"],
    "additionalProperties": False,
}


SERIAL_LOG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "device_id": {
            "type": "string",
        },
        "duration_ms": {
            "type": "integer",
            "minimum": 1,
            "default": 3000,
        },
        "max_lines": {
            "type": "integer",
            "minimum": 1,
            "default": 500,
        },
    },
    "required": ["device_id"],
    "additionalProperties": False,
}


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="build_firmware",
            description="Run the configured build command for a device.",
            inputSchema=DEVICE_ACTION_SCHEMA,
        ),
        Tool(
            name="flash_firmware",
            description="Run the configured flash command for a device.",
            inputSchema=DEVICE_ACTION_SCHEMA,
        ),
        Tool(
            name="read_serial_log",
            description="Read timestamped serial log lines from a device.",
            inputSchema=SERIAL_LOG_SCHEMA,
        ),
        Tool(
            name="reset_device",
            description="Run the configured reset command for a device.",
            inputSchema=DEVICE_ACTION_SCHEMA,
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
    result = await executor.execute(name, arguments)
    return [
        TextContent(
            type="text",
            text=json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        )
    ]


async def main() -> None:
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )
