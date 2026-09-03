#!/usr/bin/env python3
"""Cross-platform source checkout entry point for the model checker."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent
UPSTREAM_ENTRYPOINT = ROOT / "third_party" / "hlwy-ai-checker" / "start.py"


def main() -> None:
    if not UPSTREAM_ENTRYPOINT.is_file():
        raise FileNotFoundError(f"Missing upstream entrypoint: {UPSTREAM_ENTRYPOINT}")
    runpy.run_path(str(UPSTREAM_ENTRYPOINT), run_name="__main__")


if __name__ == "__main__":
    main()
