#!/usr/bin/env python3
"""Compatibility entry point kept beside the platform launchers."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_ENTRYPOINT = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"


def main() -> None:
    runpy.run_path(str(UPSTREAM_ENTRYPOINT), run_name="__main__")


if __name__ == "__main__":
    main()
