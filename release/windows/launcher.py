"""Launch the versioned ui-copy Qt dashboard in packaged Windows builds."""
from __future__ import annotations

import sys
import traceback
from ctypes import windll
from os import environ
from pathlib import Path


def _show_fatal_error(exc: Exception) -> None:
    """Persist startup diagnostics where they do not contaminate the release folder."""
    log_dir = Path(environ.get("LOCALAPPDATA", Path.home())) / "AutoXuexiPlaywright"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "launcher-error.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")
    try:
        windll.user32.MessageBoxW(
            0,
            f"程序启动失败：{exc}\n\n详细日志：{log_path}",
            "AutoXuexiPlaywright",
            0x10,
        )
    except Exception:
        pass


def main() -> None:
    """Start GUI mode unless the caller explicitly selected a mode."""
    if "--gui" not in sys.argv and "--no-gui" not in sys.argv:
        sys.argv.append("--gui")

    from autoxuexiplaywright import main as app_main

    app_main()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        _show_fatal_error(exc)
        raise
