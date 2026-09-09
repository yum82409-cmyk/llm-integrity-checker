# Changelog

## 1.0.0 - 2026-09-09

- 集成 `hlwy-ai-checker` v2.4.0，提供随机数分布指纹检测。
- 增加一键鉴别、基准标定、未知模型测试和多渠道横向评测。
- 增加可选 EvalScope 能力评测，支持 IQ、数学、知识、指令遵循和工具调用任务。
- 统一 Windows、Linux/macOS 启动入口，支持路径空格和端口冲突检查。
- 服务固定监听 `127.0.0.1`，API Key 不写入代码、任务配置或日志。
- 增加 OpenAI、Responses 和 Anthropic API 的路径处理与错误分类。
- 增加 GitHub Actions、许可证说明、安全策略和第三方许可证声明。
