from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolError:
    error_type: str
    message: str
    recoverable: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "type": self.error_type,
            "message": self.message,
            "recoverable": self.recoverable,
        }


class FirmwareMcpError(Exception):
    error_type = "RUNTIME_ERROR"
    recoverable = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def to_tool_error(self) -> ToolError:
        return ToolError(
            error_type=self.error_type,
            message=self.message,
            recoverable=self.recoverable,
        )


class ValidationError(FirmwareMcpError):
    error_type = "VALIDATION_ERROR"
    recoverable = True


class ConfigLoadError(FirmwareMcpError):
    error_type = "CONFIG_ERROR"
    recoverable = True


class DeviceNotFoundError(FirmwareMcpError):
    error_type = "DEVICE_NOT_FOUND"
    recoverable = True


class CommandExecutionError(FirmwareMcpError):
    error_type = "COMMAND_EXECUTION_ERROR"
    recoverable = True


class SerialReadError(FirmwareMcpError):
    error_type = "SERIAL_ERROR"
    recoverable = True


class UnknownToolError(FirmwareMcpError):
    error_type = "UNKNOWN_TOOL"
    recoverable = True


def success(data: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
    }


def failure(error: ToolError, data: Any = None) -> dict[str, Any]:
    return {
        "ok": False,
        "data": data,
        "error": error.to_dict(),
    }


def normalize_exception(exc: Exception) -> ToolError:
    if isinstance(exc, FirmwareMcpError):
        return exc.to_tool_error()

    return ToolError(
        error_type="INTERNAL_ERROR",
        message="unexpected internal error",
        recoverable=False,
    )
