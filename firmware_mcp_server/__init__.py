from __future__ import annotations

from pathlib import Path


SRC_PACKAGE = Path(__file__).resolve().parents[1] / "src" / "firmware_mcp_server"

if SRC_PACKAGE.is_dir():
    __path__.append(str(SRC_PACKAGE))

__version__ = "1.0.0"
