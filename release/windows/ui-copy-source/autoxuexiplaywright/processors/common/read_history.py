from datetime import date, timedelta
from json import dump, load
from os.path import isfile

from ...config import get_runtime_config
from ...storage import get_data_path

_READ_HISTORY_FILENAME = "read_history.json"


def _today_key() -> str:
    return date.today().isoformat()


def _retention_days() -> int:
    days = get_runtime_config().read_history_retention_days
    return days if days in (3, 7, 15, 30) else 7


def _load_history() -> dict[str, dict[str, list[str]]]:
    path = get_data_path(_READ_HISTORY_FILENAME)
    if not isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as reader:
            history = load(reader)
        if isinstance(history, dict):
            return history
    except Exception:
        pass
    return {}


def _save_history(history: dict[str, dict[str, list[str]]]):
    with open(get_data_path(_READ_HISTORY_FILENAME), "w", encoding="utf-8") as writer:
        dump(history, writer, ensure_ascii=False, indent=4, sort_keys=True)


def _cleanup_history(history: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, list[str]]]:
    cutoff = date.today() - timedelta(days=_retention_days() - 1)
    cleaned: dict[str, dict[str, list[str]]] = {}
    for day, day_history in history.items():
        try:
            history_day = date.fromisoformat(day)
        except ValueError:
            continue
        if history_day >= cutoff and isinstance(day_history, dict):
            cleaned[day] = day_history
    if cleaned != history:
        _save_history(cleaned)
    return cleaned


def has_read(kind: str, title: str) -> bool:
    history = _cleanup_history(_load_history())
    for day_history in history.values():
        titles = day_history.get(kind, [])
        if isinstance(titles, list) and title in titles:
            return True
    return False


def mark_read(kind: str, title: str):
    if title == "":
        return
    history = _cleanup_history(_load_history())
    today = _today_key()
    if today not in history:
        history[today] = {}
    if not isinstance(history[today].get(kind), list):
        history[today][kind] = []
    if title not in history[today][kind]:
        history[today][kind].append(title)
    _save_history(history)
