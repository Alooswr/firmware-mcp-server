from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from .config import CommandConfig
from .errors import CommandExecutionError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def run_command(config: CommandConfig, timeout_ms: int | None = None) -> dict[str, Any]:
    started_at = utc_now()
    timeout_seconds = timeout_ms / 1000 if timeout_ms else None

    try:
        process = await asyncio.create_subprocess_exec(
            *config.command,
            cwd=config.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
            timed_out = False
        except asyncio.TimeoutError:
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
            timed_out = True

        exit_code = process.returncode

        return {
            "started_at": started_at,
            "finished_at": utc_now(),
            "command": config.command,
            "cwd": config.cwd,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
        }

    except FileNotFoundError as exc:
        raise CommandExecutionError(f"command executable not found: {config.command[0]}") from exc
    except OSError as exc:
        raise CommandExecutionError("failed to start command process") from exc
