from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from datetime import datetime, timezone
from typing import Any

import serial

from .config import SerialConfig
from .errors import SerialReadError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


async def read_serial_lines(
    config: SerialConfig,
    duration_ms: int,
    max_lines: int,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    async for line in stream_serial_lines(config, duration_ms, max_lines):
        lines.append(line)
    return lines


async def stream_serial_lines(
    config: SerialConfig,
    duration_ms: int,
    max_lines: int,
):
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_lines + 1)
    stop_event = threading.Event()
    deadline = time.monotonic() + duration_ms / 1000

    def put_item(item: dict[str, Any]) -> None:
        if queue.full():
            stop_event.set()
            return
        queue.put_nowait(item)

    def producer() -> None:
        try:
            read_timeout = max(0.05, min(config.timeout_ms / 1000, 0.25))
            with serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                timeout=read_timeout,
            ) as connection:
                while not stop_event.is_set() and time.monotonic() < deadline:
                    raw = connection.readline()
                    if raw:
                        loop.call_soon_threadsafe(
                            put_item,
                            {
                                "kind": "line",
                                "timestamp": utc_now(),
                                "line": raw.decode("utf-8", errors="replace").rstrip("\r\n"),
                            },
                        )
        except serial.SerialException:
            loop.call_soon_threadsafe(
                put_item,
                {
                    "kind": "error",
                    "message": f"failed to read serial port: {config.port}",
                },
            )
        finally:
            loop.call_soon_threadsafe(put_item, {"kind": "done"})

    producer_task = asyncio.create_task(asyncio.to_thread(producer))
    try:
        line_count = 0
        while line_count < max_lines:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                break

            if item["kind"] == "line":
                line_count += 1
                yield {
                    "timestamp": item["timestamp"],
                    "line": item["line"],
                }
            elif item["kind"] == "error":
                raise SerialReadError(item["message"])
            elif item["kind"] == "done":
                break
    finally:
        stop_event.set()
        with contextlib.suppress(Exception):
            await producer_task
