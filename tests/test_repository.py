from pathlib import Path
import importlib.util
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_required_files_exist(self):
        required = (
            "LICENSE",
            "README.md",
            "pyproject.toml",
            "requirements.txt",
            "scripts/start.py",
            "scripts/start.sh",
            "scripts/Start-Model-Integrity-Checker.ps1",
            "scripts/evalscope_runner.py",
            "scripts/Install-Capability-Engine.ps1",
            "requirements-capability.txt",
            "third_party/hlwy-ai-checker/start.py",
            "third_party/hlwy-ai-checker/hlwy-ai-checker.html",
        )
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_no_personal_absolute_paths_in_source(self):
        forbidden = ("MECH" + "REVO", "MECH" + "REUO", "C:" + chr(92) + "Users" + chr(92))
        source_files = list((ROOT / "scripts").rglob("*")) + list((ROOT / "src").rglob("*"))
        for path in source_files:
            if path.is_file() and path.suffix in {".py", ".ps1", ".sh", ".cmd"}:
                text = path.read_text(encoding="utf-8")
                for value in forbidden:
                    self.assertNotIn(value, text, str(path))

    def test_openai_root_url_is_normalized(self):
        path = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"
        spec = importlib.util.spec_from_file_location("checker_server", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module._normalize_openai_base_url("https://host"), "https://host/v1")
        self.assertEqual(module._normalize_openai_base_url("https://host/v1"), "https://host/v1")

    def test_capability_config_normalizes_url_without_retaining_key(self):
        path = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"
        spec = importlib.util.spec_from_file_location("checker_capability", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config, api_key = module._validate_capability_config({
            "api_url": "https://provider.example",
            "model": "model-x",
            "api_key": "secret-value-123",
            "datasets": ["iquiz"],
            "limit": 3,
            "concurrency": 1,
        })
        self.assertEqual(config["api_url"], "https://provider.example/v1")
        self.assertEqual(api_key, "secret-value-123")
        self.assertNotIn("api_key", config)

    def test_capability_config_keeps_secret_out_of_job_config(self):
        path = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"
        spec = importlib.util.spec_from_file_location("checker_capability_server", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        config, api_key = module._validate_capability_config({
            "api_url": "https://example.test/v1",
            "api_key": "synthetic-secret-value",
            "model": "test-model",
            "datasets": ["iquiz", "gpqa_diamond"],
            "limit": 1,
            "concurrency": 1,
        })
        self.assertEqual(api_key, "synthetic-secret-value")
        self.assertNotIn("api_key", config)
        self.assertEqual(
            module._redact_secret("key=synthetic-secret-value", api_key),
            "key=[REDACTED]",
        )

    def test_capability_config_rejects_unknown_api_type(self):
        path = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"
        spec = importlib.util.spec_from_file_location("checker_capability_type", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, "不支持的 API 类型"):
            module._validate_capability_config({
                "api_url": "https://example.test/v1",
                "model": "test-model",
                "api_key": "synthetic-secret-value",
                "datasets": ["iquiz"],
                "eval_type": "unsupported",
            })


if __name__ == "__main__":
    unittest.main()
