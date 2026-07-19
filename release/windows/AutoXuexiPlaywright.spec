"""PyInstaller specification for the verified ui-copy Windows dashboard."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import collect_submodules


BUILD_ROOT = Path(SPECPATH).resolve()
SOURCE_ROOT = BUILD_ROOT / "ui-copy-source"
BROWSER_ROOT = Path(
    os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH",
        Path.home() / "AppData" / "Local" / "ms-playwright",
    ),
)

if not (SOURCE_ROOT / "autoxuexiplaywright" / "__init__.py").is_file():
    raise SystemExit(f"Missing packaged dashboard source: {SOURCE_ROOT}")

sys.path.insert(0, str(SOURCE_ROOT))


def _latest_firefox(browser_root: Path) -> Path:
    """Return the installed Playwright Firefox payload used by the release."""
    candidates = sorted(browser_root.glob("firefox-*"))
    if not candidates:
        raise SystemExit(
            "Playwright Firefox is missing. Run `playwright install firefox` first or "
            "set PLAYWRIGHT_BROWSERS_PATH."
        )
    return candidates[-1]


datas = [
    (
        str(SOURCE_ROOT / "autoxuexiplaywright" / "resources"),
        "autoxuexiplaywright/resources",
    ),
]
binaries = []
hiddenimports = collect_submodules("autoxuexiplaywright")

playwright_data, playwright_binaries, playwright_hidden = collect_all("playwright")
datas += playwright_data
binaries += playwright_binaries
hiddenimports += playwright_hidden

for package_name in ("m3u8", "pyzbar", "qrcode", "PIL", "ffmpeg", "magic", "iso8601"):
    package_data, package_binaries, package_hidden = collect_all(package_name)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_hidden

firefox = _latest_firefox(BROWSER_ROOT)
datas.append(
    (
        str(firefox),
        f"playwright/driver/package/.local-browsers/{firefox.name}",
    ),
)

analysis = Analysis(
    [str(BUILD_ROOT / "launcher.py")],
    pathex=[str(SOURCE_ROOT), str(BUILD_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["patchright", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AutoXuexiPlaywright",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(BUILD_ROOT / "app.ico"),
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="AutoXuexiPlaywright",
)
