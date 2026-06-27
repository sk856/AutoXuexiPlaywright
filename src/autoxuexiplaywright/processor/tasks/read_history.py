"""Persist read history by date."""

import json as _json
from datetime import date as _date
from pathlib import Path as _Path
from autoxuexiplaywright.storage import get_data_path as _get_data_path


_READ_HISTORY_PATH = _get_data_path(_Path("read_history.json"))


def _today_key() -> str:
    return _date.today().isoformat()


def _load_history() -> dict[str, dict[str, list[str]]]:
    if not _READ_HISTORY_PATH.is_file():
        return {}
    try:
        history = _json.loads(_READ_HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return history if isinstance(history, dict) else {}


def _save_history(history: dict[str, dict[str, list[str]]]):
    _READ_HISTORY_PATH.write_text(
        _json.dumps(history, ensure_ascii=False, indent=4, sort_keys=True),
        encoding="utf-8",
    )


def has_read(kind: str, title: str) -> bool:
    """Check whether title has been read today."""
    today_history = _load_history().get(_today_key(), {})
    titles = today_history.get(kind, [])
    return title in titles


def mark_read(kind: str, title: str):
    """Mark title as read today."""
    history = _load_history()
    today = _today_key()
    history.setdefault(today, {})
    history[today].setdefault(kind, [])
    if title not in history[today][kind]:
        history[today][kind].append(title)
    _save_history(history)
