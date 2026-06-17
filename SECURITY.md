# Security Policy

[中文文档](SECURITY.zh-CN.md)

## Supported Versions

The `main` branch receives security fixes. Releases are not currently maintained
as separate long-term support branches.

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability.

Report security issues privately to the repository owner through GitHub contact
channels. Include:

- A short description of the issue.
- A minimal reproduction or proof of concept, if available.
- The affected operating system and Python version.
- Whether the issue requires a malicious `devices.json` file or can be triggered
  by an MCP client alone.

## Operational Guidance

Firmware MCP Server is a local automation bridge. It intentionally runs local
commands configured by the user. Treat the device configuration as trusted input.

Recommended practices:

- Keep `config/devices.json` private and machine-local.
- Review configured build, flash, reset, and serial settings before connecting
  an MCP client.
- Avoid pointing commands at scripts or binaries from untrusted repositories.
- Use a dedicated working directory for build output and logs.
- Run the server with the least privileges required for your device tooling.
- Do not expose stdio transport through an unauthenticated network wrapper.

Built-in safety properties:

- The server does not start an HTTP listener.
- External commands are executed without `shell=True`.
- Local device configuration is ignored by git by default.
- stdout is reserved for MCP protocol traffic, reducing accidental protocol
  corruption.
