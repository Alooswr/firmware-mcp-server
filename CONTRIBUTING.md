# Contributing

Thank you for your interest in contributing to Firmware MCP Server.

[中文文档](CONTRIBUTING.zh-CN.md)

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

Create a local device config before running the server:

```bash
cp config/devices.example.json config/devices.json
```

## Test

```bash
python -m unittest discover -s tests
```

## Pull Request Guidelines

- Keep changes focused and easy to review.
- Do not commit local `config/devices.json` files, logs, virtual environments,
  or Python cache files.
- Add or update tests when behavior changes.
- Keep stdout reserved for MCP protocol traffic. Runtime logs should go to
  stderr.
- Prefer explicit argument arrays for external commands. Do not introduce
  `shell=True` unless there is a strong, documented reason.
- Update both English and Chinese documentation when user-facing behavior
  changes.

## Commit Messages

Use short imperative commit messages, for example:

```text
Add serial timeout validation
Document MCP client configuration
```
