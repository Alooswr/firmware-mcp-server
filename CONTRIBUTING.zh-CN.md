# 贡献指南

感谢你对 Firmware MCP Server 的贡献兴趣。

[English](CONTRIBUTING.md)

## 开发环境

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Windows Command Prompt：

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
```

运行服务器前，先创建本地设备配置：

```bash
cp config/devices.example.json config/devices.json
```

## 测试

```bash
python -m unittest discover -s tests
```

## Pull Request 要求

- 保持改动聚焦，便于 review。
- 不要提交本地 `config/devices.json`、日志、虚拟环境或 Python 缓存文件。
- 修改行为时同步新增或更新测试。
- stdout 保留给 MCP 协议通信，运行日志应输出到 stderr。
- 外部命令优先使用显式参数数组。除非有充分且已记录的理由，否则不要引入 `shell=True`。
- 用户可见行为变化时，同时更新英文和中文文档。

## 提交信息

提交信息建议使用简短的祈使句，例如：

```text
Add serial timeout validation
Document MCP client configuration
```
