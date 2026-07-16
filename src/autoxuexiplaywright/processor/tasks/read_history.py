"""Persist read history by date."""

import json as _json
from pathlib import Path as _Path
from datetime import date as _date
from datetime import timedelta as _timedelta
from autoxuexiplaywright.storage import get_data_path as _get_data_path


_READ_HISTORY_PATH = _get_data_path(_Path("read_history.json"))
_VALID_RETENTION_DAYS = (3, 7, 15, 30)
_retention_days = 7


def set_read_history_retention_days(days: int):
    """Set how long read history should be kept and checked."""
    global _retention_days  # noqa: PLW0603
    _retention_days = days if days in _VALID_RETENTION_DAYS else 7


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


def _cleanup_history(
    history: dict[str, dict[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    cutoff = _date.today() - _timedelta(days=_retention_days - 1)
    cleaned: dict[str, dict[str, list[str]]] = {}
    for day, day_history in history.items():
        try:
            history_day = _date.fromisoformat(day)
        except ValueError:
            continue
        if history_day >= cutoff and isinstance(day_history, dict):
            cleaned[day] = day_history
    if cleaned != history:
        _save_history(cleaned)
    return cleaned


def has_read(kind: str, title: str) -> bool:
    """Check whether title has been read within the retention window."""
    history = _cleanup_history(_load_history())
    for day_history in history.values():
        titles = day_history.get(kind, [])
        if isinstance(titles, list) and title in titles:
            return True
    return False


def mark_read(kind: str, title: str):
    """Mark title as read today."""
    if title == "":
        return
    history = _cleanup_history(_load_history())
    today = _today_key()
    history.setdefault(today, {})
    if not isinstance(history[today].get(kind), list):
        history[today][kind] = []
    if title not in history[today][kind]:
        history[today][kind].append(title)
    _save_history(history)
