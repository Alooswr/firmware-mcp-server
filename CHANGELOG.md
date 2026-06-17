# Changelog

All notable changes to this project will be documented in this file.

This project uses a simple changelog format inspired by Keep a Changelog.

## [1.0.0] - 2026-06-17

### Added

- Initial open source release.
- Local stdio MCP server for embedded firmware automation.
- `build_firmware`, `flash_firmware`, `reset_device`, and `read_serial_log`
  tools.
- Local JSON device configuration with hot reload.
- Per-device execution locks.
- Subprocess execution without `shell=True`.
- Serial log capture with timestamped lines.
- Internal diagnostic timeline and deterministic failure classification.
- English and Chinese documentation.
