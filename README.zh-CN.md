# Firmware MCP Server

[English](README.md)

<p align="center">
  <img src="assets/mascot-catgirl.jpg" alt="Firmware MCP Server 猫娘吉祥物" width="320">
</p>

Firmware MCP Server 是一个本地 stdio MCP 服务器，用于嵌入式固件自动化。它通过本地设备配置文件暴露一组小而明确的 MCP 工具，让客户端可以构建固件、烧录设备、复位设备，并采集带时间戳的串口日志。

这个项目面向本机工作站自动化场景：不启动 HTTP 服务，不通过 shell 执行命令，并默认把本机设备路径排除在版本控制之外。

## 功能特性

- 仅使用 stdio 的本地 MCP 服务器。
- 提供四个固件工具：构建、烧录、复位、串口日志采集。
- 同一 `device_id` 的操作使用异步锁串行执行。
- 不同设备之间可以并发执行。
- 设备配置文件变化后自动热加载。
- 子进程通过 `asyncio.create_subprocess_exec` 执行。
- 命令参数使用显式数组，不传给 `shell=True`。
- 串口采集基于 `pyserial`，运行时通过 stderr 增量输出 JSON 追踪事件。
- 成功和失败响应使用统一 JSON envelope。
- 内置轻量诊断逻辑，可根据工具追踪和串口日志模式做确定性分类。

## 工具列表

| 工具 | 用途 |
| --- | --- |
| `build_firmware` | 执行某个设备配置好的构建命令。 |
| `flash_firmware` | 执行某个设备配置好的烧录命令。 |
| `reset_device` | 执行某个设备可选的复位命令。 |
| `read_serial_log` | 读取某个设备带时间戳的串口日志。 |

`build_firmware`、`flash_firmware`、`reset_device` 的输入：

```json
{
  "device_id": "demo",
  "timeout_ms": 300000
}
```

`timeout_ms` 是可选参数。

`read_serial_log` 的输入：

```json
{
  "device_id": "demo",
  "duration_ms": 3000,
  "max_lines": 500
}
```

`duration_ms` 和 `max_lines` 是可选参数。

## 响应格式

每个工具都会返回一个 JSON 对象，并以 MCP text content 的形式传递。

成功响应：

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

参数校验或运行时失败：

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

命令失败时，捕获到的进程信息会保留在 `data` 中：

```json
{
  "ok": false,
  "data": {
    "device_id": "demo",
    "action": "build_firmware",
    "started_at": "2026-01-01T00:00:00.000Z",
    "finished_at": "2026-01-01T00:00:02.000Z",
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

## 环境要求

- Python 3.10 或更新版本。
- 一个兼容 MCP 的本地客户端。
- 使用串口日志采集时需要 `pyserial`。
- 每个设备需要配置本机可执行的构建、烧录或复位命令。

## 安装

克隆仓库：

```bash
git clone https://github.com/Alooswr/firmware-mcp-server.git
cd firmware-mcp-server
```

创建虚拟环境：

```bash
python -m venv .venv
```

Windows 激活虚拟环境：

```bat
.venv\Scripts\activate
```

Linux 或 macOS 激活虚拟环境：

```bash
source .venv/bin/activate
```

以可编辑模式安装项目：

```bash
python -m pip install -e .
```

也可以只安装依赖：

```bash
python -m pip install -r requirements.txt
```

## 设备配置

默认设备配置路径：

```text
./config/devices.json
```

从示例文件创建本地配置：

```bash
cp config/devices.example.json config/devices.json
```

Windows Command Prompt：

```bat
copy config\devices.example.json config\devices.json
```

`config/devices.json` 默认被 git 忽略，因为它通常包含本机路径、串口号和私有构建命令。

可以通过 `FIRMWARE_MCP_DEVICES_CONFIG` 覆盖配置路径。

Linux 或 macOS：

```bash
export FIRMWARE_MCP_DEVICES_CONFIG=/path/to/devices.json
```

Windows Command Prompt：

```bat
set FIRMWARE_MCP_DEVICES_CONFIG=C:\path\to\devices.json
```

设备条目结构：

```json
{
  "device_id": "demo",
  "build": {
    "command": ["make"],
    "cwd": "/path/to/firmware/project"
  },
  "flash": {
    "command": ["make", "flash"],
    "cwd": "/path/to/firmware/project"
  },
  "reset": {
    "command": ["python", "scripts/reset.py"],
    "cwd": "/path/to/firmware/project"
  },
  "serial": {
    "port": "COM3",
    "baudrate": 115200,
    "timeout_ms": 3000
  }
}
```

说明：

- `device_id` 必须唯一。
- `build`、`flash`、`serial` 是必填项。
- `reset` 是可选项。
- `cwd` 是可选项。
- `command` 必须是非空字符串数组。
- 命令会被直接执行，不会由 shell 解释。

## MCP 客户端配置

从克隆仓库运行时的客户端配置示例：

```json
{
  "mcpServers": {
    "firmware": {
      "command": "python",
      "args": ["-m", "firmware_mcp_server"],
      "cwd": "/absolute/path/to/firmware-mcp-server"
    }
  }
}
```

显式指定设备配置文件的示例：

```json
{
  "mcpServers": {
    "firmware": {
      "command": "python",
      "args": ["-m", "firmware_mcp_server"],
      "cwd": "/absolute/path/to/firmware-mcp-server",
      "env": {
        "FIRMWARE_MCP_DEVICES_CONFIG": "/absolute/path/to/devices.json"
      }
    }
  }
}
```

## 本地运行

在项目根目录执行：

```bash
python -m firmware_mcp_server
```

该进程通过 stdio 进行 MCP 通信。常规运行追踪会以紧凑 JSON 日志事件的形式输出到 stderr。

## 诊断能力

运行时维护一条内存中的诊断时间线，把工具执行追踪和串口事件合并起来。这个内部诊断层不会增加公开 MCP 工具，也不会改变工具响应格式。

串口事件会被标记为以下语义状态：

- `BOOT`
- `CRASH`
- `HANG`
- `REBOOT_LOOP`
- `UNKNOWN`

确定性分类器可能返回的失败类型包括：

- `BUILD_FAILED`
- `FLASH_FAILED`
- `RESET_FAILED`
- `CRASH_AFTER_FLASH`
- `REBOOT_LOOP`
- `NO_BOOT`
- `UNKNOWN`

工具执行追踪示例：

```json
{
  "event": "tool_execution_trace",
  "tool_name": "build_firmware",
  "device_id": "demo",
  "start_time": "2026-01-01T00:00:00.000Z",
  "end_time": "2026-01-01T00:00:02.000Z",
  "status": "ok"
}
```

串口追踪示例：

```json
{
  "event": "serial_log_line",
  "source": "serial",
  "device_id": "demo",
  "port": "COM3",
  "timestamp": "2026-01-01T00:00:00.000Z",
  "line": "boot",
  "state": "BOOT"
}
```

## 开发

安装开发环境：

```bash
python -m pip install -e .
```

运行测试：

```bash
python -m unittest discover -s tests
```

检查被忽略的本地文件：

```bash
git status --ignored --short
```

## 安全模型

这个服务器会执行设备配置中的本地命令。请把 `devices.json` 视为可信本地配置，并在 MCP 客户端使用前审查其中的命令。

重要默认行为：

- 不启动 HTTP 监听。
- 命令执行不使用 `shell=True`。
- 本机设备配置默认不进入 git。
- stdout 保留给 MCP 协议通信。
- 日志和追踪输出到 stderr。

漏洞报告和运行安全建议见 [SECURITY.zh-CN.md](SECURITY.zh-CN.md)。

## 贡献

欢迎贡献。提交 pull request 前请阅读 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)。

## 许可证

本项目使用 [MIT License](LICENSE)。

图片资产的说明见 [ASSETS.md](ASSETS.md)。
