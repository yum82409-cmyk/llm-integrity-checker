from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
