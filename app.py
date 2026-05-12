"""Convenience launcher for running the project from the repository root.

This file makes the src-layout package importable without requiring an editable
install first. That keeps local development simple: `python app.py` is enough.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Resolve the repository root and the src directory once at import time.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"

# Prepend src to sys.path so the local package can be imported directly.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from diced.main import main


if __name__ == "__main__":
    main()