# llm-integrity-checker

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-555555)](#环境要求)
[![License](https://img.shields.io/badge/License-MIT-2ea44f)](./LICENSE)
[![Upstream](https://img.shields.io/badge/Upstream-LGPL--2.1-orange)](https://github.com/hanlinwenyuan/hlwy-ai-checker)

基于随机数分布指纹的第三方大模型 API 完整性检测工具。它用于辅助判断渠道是否使用了所声明的模型，并识别模型替换、量化、采样配置变化或明显能力缩水。

> 这不是心理学意义上的 IQ 测试，也不会产生可信的“智商值”。它是一个统计一致性检测器，任何结论都应结合多轮测试和真实任务交叉验证。

## 特性

- 一键鉴别：直接使用公开官方基准进行快速初筛。
- 基准标定：用可信的官方 API 建立特定模型的行为基准。
- 渠道测试：比较第三方渠道与官方基准的分布相似度。
- 大横评：用同一模型和测试参数对多个渠道进行横向比较。
- 本地优先：代理服务仅绑定 `127.0.0.1`，API Key 不写入代码、日志或静态配置。
- Windows 兼容：支持路径空格、固定启动目录、非 UTF-8 控制台和端口冲突检测。
- 中转站兼容：OpenAI 兼容接口填写服务根地址或带 `/v1` 的地址均可，代理会规范化到正确 API 路径。
- 跨平台启动：提供 PowerShell、CMD、POSIX shell 和 Python 入口。

## 核心原理

大语言模型在“从 1 到 355 随机选择一个数字”这类请求上并不是真正均匀的随机数生成器。训练数据、模型架构、分词、对齐方式和采样实现会使输出产生可重复的统计偏差。

工具重复采样，计算输出分布、众数、均值、标准差、唯一值数量等统计特征，再与官方基准比较，得到行为指纹相似度。样本越少，随机波动越大；建议快速初筛使用 100 次左右，正式判断使用 200 次以上并重复 2–3 轮。

该方法只能回答“行为是否与基准一致”，不能单独证明服务商实际部署了某个模型，也不能替代安全审计、合同核验或完整能力评测。

## 架构

```text
.
├── scripts/
│   ├── start.py                         # 跨平台 Python 启动入口
│   ├── start.sh                         # Linux/macOS 启动器
│   └── Start-Model-Integrity-Checker.ps1 # Windows 启动器
├── src/llm_integrity_checker/           # 项目自有 Python 包元数据
├── third_party/hlwy-ai-checker/         # 上游前端、代理和 LGPL 通知
├── tests/                               # 仓库布局和安全回归测试
├── pyproject.toml
├── requirements.txt
├── SECURITY.md
└── THIRD_PARTY_NOTICES.md
```

## 环境要求

- Python 3.10 或更高版本
- 可访问目标 API 和官方基准源的网络环境
- OpenAI 兼容 API，或页面支持的 Responses/Anthropic API 格式

API Key 需要由使用者在本地页面中临时输入。项目不会提供、保存或代管任何密钥。

## 快速启动

### Windows PowerShell

```powershell
cd 'C:\path\to\llm-integrity-checker'
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\Start-Model-Integrity-Checker.ps1
```

也可以双击根目录的 `Start-Model-Integrity-Checker.cmd`。

自定义端口：

```powershell
.\scripts\Start-Model-Integrity-Checker.ps1 -Port 18080
```

### Linux/macOS

```bash
cd /path/to/llm-integrity-checker
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./scripts/start.sh
```

浏览器打开 `http://127.0.0.1:8000`。如端口被占用，可设置 `HLWY_PORT=18080`。

## 推荐检测流程

1. 在“一键鉴别”中选择已有官方基准的模型。
2. 填写渠道 Base URL、模型名和 API Key；OpenAI 兼容中转站可填 `https://host` 或 `https://host/v1`。
3. 初筛后，把采样次数提高到 200 以上重复测试。
4. 在不同时间重复 2–3 轮，观察结论是否稳定。
5. 对异常渠道再使用真实代码、长上下文和工具调用任务交叉验证。
6. 没有公开基准的模型，先在“标定基准”中使用可信官方渠道建立基准。

## 安全声明

- 服务硬绑定 `127.0.0.1`，不应直接暴露到局域网或公网。
- 请求体和 API Key 不写入项目日志；不要在代理、浏览器扩展或终端历史中泄露密钥。
- `.gitignore` 排除 `.env`、密钥文件、日志、缓存、虚拟环境和生成压缩包。
- 检测结果仅供技术判断参考，不作为商业纠纷、退款或法律事实的唯一依据。
- 详见 [SECURITY.md](./SECURITY.md)。

## 开发与验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts src third_party/hlwy-ai-checker/start.py
```

持续集成配置位于 `.github/workflows/ci.yml`，覆盖 Python 3.10、3.11 和 3.12。

## 许可证与上游致谢

本项目自有的启动器、元数据、测试和文档使用 [MIT License](./LICENSE)。

检测器核心页面和代理基于 [hanlinwenyuan/hlwy-ai-checker](https://github.com/hanlinwenyuan/hlwy-ai-checker) v2.4.0 二次开发集成。上游衍生文件继续遵循 GNU LGPL v2.1，详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) 和 `third_party/hlwy-ai-checker/LICENSE`。

## GitHub 发布

初始化并提交：

```bash
git init
git add .
git commit -m "feat: initial release of model integrity checker v1.0.0"
```

创建并推送公开仓库：

```bash
gh auth login
gh repo create llm-integrity-checker --public --source=. --remote=origin --push
```

如果远程仓库已经存在：

```bash
git remote add origin https://github.com/<YOUR_USERNAME>/llm-integrity-checker.git
git push -u origin main
```
