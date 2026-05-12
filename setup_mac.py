"""Build a tiny native macOS app bundle for RollCoaster.

Usage:
    python setup_mac.py
"""

from __future__ import annotations

import os
import plistlib
import shutil
import stat
from pathlib import Path


APP_NAME = "RollCoaster"
BUNDLE_ID = "com.rollcoaster.app"
VERSION = "0.1.0"

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
APP_DIR = DIST_DIR / f"{APP_NAME}.app"
CONTENTS_DIR = APP_DIR / "Contents"
MACOS_DIR = CONTENTS_DIR / "MacOS"
RESOURCES_DIR = CONTENTS_DIR / "Resources"
ICON_FILE = PROJECT_ROOT / "assets" / "RollCoaster.icns"
ICON_NAME = "RollCoaster.icns"


def _resolve_python() -> str:
    """Prefer the project venv Python, fallback to python3 on PATH."""
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return os.environ.get("PYTHON", "python3")


def _build_launcher_script(python_path: str) -> str:
    return f"""#!/bin/bash
set -euo pipefail
exec \"{python_path}\" \"{(PROJECT_ROOT / 'mac_app.py').as_posix()}\"
"""


def build_app_bundle() -> Path:
    """Create a minimal .app bundle that launches the Tkinter GUI."""
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    MACOS_DIR.mkdir(parents=True, exist_ok=True)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    launcher_path = MACOS_DIR / APP_NAME
    launcher_path.write_text(_build_launcher_script(_resolve_python()), encoding="utf-8")

    mode = launcher_path.stat().st_mode
    launcher_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if ICON_FILE.exists():
        shutil.copy2(ICON_FILE, RESOURCES_DIR / ICON_NAME)

    info_plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundlePackageType": "APPL",
        "CFBundleIconFile": ICON_NAME,
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
    }

    with (CONTENTS_DIR / "Info.plist").open("wb") as fp:
        plistlib.dump(info_plist, fp)

    return APP_DIR


def main() -> None:
    app_path = build_app_bundle()
    print(f"Built app bundle: {app_path}")


if __name__ == "__main__":
    main()
