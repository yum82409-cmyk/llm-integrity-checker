# 贡献指南

## 开发环境

需要 Python 3.10 或更高版本。基础依赖安装方式：

```bash
python -m pip install -r requirements.txt
```

能力评测依赖是可选项，不参与基础测试套件。

## 提交前检查

```bash
python -m unittest discover -s tests -v
python -m compileall -q scripts src third_party/hlwy-ai-checker/start.py
git diff --check
```

提交信息使用 Conventional Commits，例如：

```text
fix: improve Anthropic URL normalization
```

## 安全要求

- 不提交 API Key、访问令牌、请求体、日志和本地测试结果。
- 不把服务监听地址改为 `0.0.0.0`，除非完成独立安全评审。
- 修改上游衍生文件时，保留上游版权和 LGPL v2.1 许可边界。
- 报告安全问题时遵循 [SECURITY.md](./SECURITY.md)，不要公开粘贴凭据。
