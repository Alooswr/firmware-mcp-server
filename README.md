# Firmware MCP Server

Production-grade local stdio MCP server for embedded firmware automation.

## Tools

- `build_firmware`
- `flash_firmware`
- `read_serial_log`
- `reset_device`

All tools accept JSON input and return one JSON object:

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

On failure:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "error_type": "VALIDATION_ERROR",
    "type": "VALIDATION_ERROR",
    "message": "device_id must be a non-empty string",
    "recoverable": true
  }
}
```

Command failures keep captured process details in `data`:

```json
{
  "ok": false,
  "data": {
    "device_id": "demo",
    "action": "build_firmware",
    "started_at": "ISO-8601",
    "finished_at": "ISO-8601",
    "command": ["make"],
    "cwd": "/path/to/project",
    "exit_code": 2,
    "timed_out": false,
    "stdout": "",
    "stderr": "make error"
  },
  "error": {
    "error_type": "BUILD_FAILED",
    "type": "BUILD_FAILED",
    "message": "build_firmware exited with code 2 for device: demo",
    "recoverable": true
  }
}
```

## Runtime Guarantees

- Python stdio MCP server only.
- No HTTP server.
- No stdout pollution outside MCP protocol.
- Build, flash, reset, and serial read are isolated behind `ToolExecutor`.
- Device config is loaded at startup and reparsed only when the config file changes.
- Same `device_id` operations are serialized with a per-device async lock.
- Different devices can run concurrently.
- Subprocess execution uses `asyncio.create_subprocess_exec`.
- Commands are arrays and are never executed through `shell=True`.
- Serial log capture uses `pyserial` through a background producer and async queue.
- Serial log lines are emitted incrementally to stderr as JSON log events while the tool is running.
- Each tool call emits one stderr execution trace event with tool name, device id, start time, end time, and status.

Serial stream event example:

```json
{
  "event": "serial_log_line",
  "source": "serial",
  "device_id": "demo",
  "port": "COM3",
  "timestamp": "ISO-8601",
  "line": "boot"
}
```

Tool execution trace example:

```json
{
  "event": "tool_execution_trace",
  "tool_name": "build_firmware",
  "device_id": "demo",
  "start_time": "ISO-8601",
  "end_time": "ISO-8601",
  "status": "ok"
}
```

## Diagnostics

The runtime includes a lightweight internal diagnostic layer. It does not add tools and does not change MCP output.

Serial events are tagged with semantic states:

- `BOOT`
- `CRASH`
- `HANG`
- `REBOOT_LOOP`
- `UNKNOWN`

`ToolExecutor.diagnostic_timeline(device_id)` merges cached tool traces and serial events into one ordered timeline.

`ToolExecutor.classify_diagnostics(device_id)` applies deterministic rules and returns:

```json
{
  "failure_type": "CRASH_AFTER_FLASH",
  "message": "crash observed after flash activity"
}
```

## Install

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Device Config

Default config path:

```text
./config/devices.json
```

Create a local config from the example:

```bash
cp config/devices.example.json config/devices.json
```

`config/devices.json` is intentionally ignored by git so local paths, serial ports, and private build commands do not get committed.

Override with:

```text
FIRMWARE_MCP_DEVICES_CONFIG
```

Linux/macOS:

```bash
export FIRMWARE_MCP_DEVICES_CONFIG=/path/to/devices.json
```

Windows:

```bat
set FIRMWARE_MCP_DEVICES_CONFIG=C:\path\to\devices.json
```

Example device entry:

```json
{
  "device_id": "string",
  "build": {
    "command": ["arg1", "arg2", "..."],
    "cwd": "string"
  },
  "flash": {
    "command": ["arg1", "arg2", "..."],
    "cwd": "string"
  },
  "reset": {
    "command": ["arg1", "arg2", "..."]
  },
  "serial": {
    "port": "string",
    "baudrate": 115200,
    "timeout_ms": 3000
  }
}
```

`reset` is optional. `cwd` is optional. `command` must be a string array.

## Run Locally

From the project root:

```bash
python -m firmware_mcp_server
```

Compatible source-layout entrypoint:

```bash
python -m src.firmware_mcp_server
```

## MCP Client Example

```json
{
  "mcpServers": {
    "firmware": {
      "command": "python",
      "args": ["-m", "firmware_mcp_server"],
      "cwd": "/path/to/firmware-mcp-server"
    }
  }
}
```

## Tool Inputs

`build_firmware`, `flash_firmware`, and `reset_device`:

```json
{
  "device_id": "string"
}
```

Optional timeout:

```json
{
  "device_id": "string",
  "timeout_ms": 300000
}
```

`read_serial_log`:

```json
{
  "device_id": "string",
  "duration_ms": 3000,
  "max_lines": 500
}
```

## Tests

```bash
python -m unittest discover -s tests
```

## License

MIT
