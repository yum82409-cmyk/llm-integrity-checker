# 模型防掺水检测器

本目录集成了开源项目 `hanlinwenyuan/hlwy-ai-checker` 的稳定版 **v2.4.0**，用于比较第三方 API 渠道与官方基准的随机数分布指纹。

## 重要说明

- 它不是医学或心理学意义上的 IQ 测试，也不会输出可信的“智商值”。
- 它检测的是**模型行为统计指纹是否与基准一致**，可辅助发现换模型、量化、采样参数改变或明显降智。
- 统计结果不是绝对证据。建议至少 200 次采样并重复 2–3 轮，再结合真实推理/代码任务交叉验证。
- API Key 不写入本地配置文件；它只由浏览器页面提交给本机代理，再转发到你填写的 API 地址。

## 启动

在 `ai-dev-bootstrap` 目录双击：

```text
Start-Model-Integrity-Checker.cmd
```

或在 PowerShell 中运行：

```powershell
.\Start-Model-Integrity-Checker.ps1
```

可改端口：

```powershell
.\Start-Model-Integrity-Checker.ps1 -Port 18080
```

首次启动会在 `%LOCALAPPDATA%\AI-Dev-Bootstrap\ModelIntegrityCheckerRuntime` 创建隔离的 Python 虚拟环境并安装 `requests`。

## 推荐检测流程

1. 优先使用“一键鉴别”，选择已有官方基准的模型。
2. Base URL 必须包含 `/v1`（按渠道实际格式填写）。
3. 模型名称必须与渠道真实暴露的名称完全一致。
4. 快速初筛可用 40–100 次；正式判断建议 200 次以上。
5. 同一渠道在不同时间重复测试 2–3 轮。
6. 没有官方基准的模型，先用官方 API 在“标定基准”页标定，再测试第三方渠道。
7. 在“大横评”里用同一模型比较多个渠道，但不要把一次排名当成绝对结论。

## 本地集成改动

相对上游 v2.4.0，本集成只做运行与安全加固：

- 支持通过 `HLWY_PORT` 修改端口；
- 支持 `HLWY_NO_BROWSER=1`，便于自动健康检查；
- 静态文件按脚本所在目录读取；
- 添加 `/health` 健康检查；
- 服务强制绑定 `127.0.0.1`；
- CORS 只允许同端口的本机页面，不再允许任意网页调用代理。

## 上游与许可

- 上游项目：https://github.com/hanlinwenyuan/hlwy-ai-checker
- 上游版本：2.4.0，发布于 2026-08-28
- 下载包 SHA-256：`B928A3A09C3EB505A5A610B451FB112CD8F247A409162396262C812A3695438B`
- 许可证：GNU LGPL v2.1，见 `LICENSE`
