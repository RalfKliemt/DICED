"""Build a tiny native macOS app bundle for DICED.

Usage:
    python setup_mac.py
"""

from __future__ import annotations

import os
import plistlib
import shutil
import stat
import subprocess
import sys
from pathlib import Path


APP_NAME = "DICED"
BUNDLE_ID = "com.diced.app"
VERSION = "0.1.0"

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
APP_DIR = DIST_DIR / f"{APP_NAME}.app"
CONTENTS_DIR = APP_DIR / "Contents"
MACOS_DIR = CONTENTS_DIR / "MacOS"
RESOURCES_DIR = CONTENTS_DIR / "Resources"
ICON_SET_DIR = PROJECT_ROOT / "assets" / "DICED.iconset"
ICON_NAME = "DICED.icns"


def _generate_icns(resources_dir: Path) -> Path:
    """Generate .icns dynamically from .iconset and place it directly into the app bundle.
    
    The .icns file is never stored on disk outside the build — it's created fresh
    each time and only lives inside Contents/Resources/ of the app bundle.
    
    Returns the path to the generated .icns file, or None if generation failed.
    """
    icns_path = resources_dir / ICON_NAME
    
    if not ICON_SET_DIR.exists():
        print("  Warning: DICED.iconset not found.", file=sys.stderr)
        return None
    
    print("  Generating .icns from iconset...")
    try:
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(ICON_SET_DIR), "-o", str(icns_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and icns_path.exists():
            print("  .icns generated and bundled.")
            return icns_path
        else:
            stderr = result.stderr.strip()
            print(f"  Warning: iconutil failed: {stderr}", file=sys.stderr)
    except FileNotFoundError:
        print("  Warning: iconutil not found (macOS only).", file=sys.stderr)
    
    return None


def _resolve_python() -> str:
    """Find the best Python at build time and return its absolute path.

    Priority:
    1. Project venv Python (known to work with all dependencies).
    2. Homebrew arm64 Python (/opt/homebrew).
    3. Homebrew Intel Python (/usr/local).
    Falls back to 'python3' only as a last resort.
    """
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        # Resolve symlinks to get the real binary path.
        return str(venv_python.resolve())
    for candidate in [
        Path("/opt/homebrew/bin/python3"),
        Path("/usr/local/bin/python3"),
    ]:
        if candidate.exists():
            return str(candidate)
    return "python3"


def _build_launcher_script(python_path: str) -> str:
    """Build a bash launcher that uses the given Python binary.

    Embedding the path at build time avoids picking up Xcode's Python 3.9
    (which ships with Tcl/Tk 8.5 that panics in TkpInit on modern macOS)
    when the app is launched via launchd, where Homebrew's PATH is not active.
    """
    return f"""#!/bin/bash
set -euo pipefail

# Get the directory containing this script (MacOS/)
SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
RESOURCES_DIR="${{SCRIPT_DIR}}/../Resources"

export PYTHONPATH="${{RESOURCES_DIR}}/lib:${{PYTHONPATH:-}}"
export PYTHONDONTWRITEBYTECODE=1

# Python binary resolved at build time — never picks up Xcode Python 3.9
# via PATH when double-clicked (launchd does not source ~/.zshrc / brew PATH).
exec "{python_path}" -c "
import sys, os
resources_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), \'..\', \'Resources\')
)
lib_dir = os.path.join(resources_dir, \'lib\')
if os.path.isdir(lib_dir):
    sys.path.insert(0, lib_dir)
from diced.main import main
main()
" "$@"
"""


def _copy_package_tree(src: Path, dst: Path) -> None:
    """Recursively copy a directory, handling .pyc and __pycache__ exclusion."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_dir():
            if item.name in ("__pycache__", ".pytest_cache", "*.egg-info"):
                continue
            _copy_package_tree(item, dst / item.name)
        else:
            if not item.name.endswith(".pyc"):
                shutil.copy2(item, dst / item.name)


def build_app_bundle() -> Path:
    """Create a minimal .app bundle that launches the Tkinter GUI.
    
    This makes the app self-contained by bundling the Python package.
    Uses a Python launcher for better environment control.
    """
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    MACOS_DIR.mkdir(parents=True, exist_ok=True)
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    # Create the lib directory where we'll bundle the Python package
    lib_dir = RESOURCES_DIR / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    # Copy the diced package to Resources/lib
    src_diced = PROJECT_ROOT / "src" / "diced"
    dst_diced = lib_dir / "diced"
    _copy_package_tree(src_diced, dst_diced)

    # Resolve the Python binary at build time and embed it in the launcher.
    python_path = _resolve_python()
    print(f"  Python: {python_path}")

    launcher_path = MACOS_DIR / APP_NAME
    launcher_path.write_text(_build_launcher_script(python_path), encoding="utf-8")

    # Make it executable
    mode = launcher_path.stat().st_mode
    launcher_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Generate .icns dynamically and bundle it directly into Resources
    icns_path = _generate_icns(RESOURCES_DIR)

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
