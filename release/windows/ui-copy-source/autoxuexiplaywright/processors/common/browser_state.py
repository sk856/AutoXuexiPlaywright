from json import dump, dumps, load
from os.path import isfile
from typing import Any

from ...logger import debug, warning
from ...storage import get_cache_path

_STORAGE_STATE_FILENAME = "cookies.json"
_SESSION_STORAGE_FILENAME = "session_storage.json"


def get_storage_state_path() -> str:
    return get_cache_path(_STORAGE_STATE_FILENAME)


def _get_session_storage_path() -> str:
    return get_cache_path(_SESSION_STORAGE_FILENAME)


def has_storage_state() -> bool:
    return isfile(get_storage_state_path())


def _load_session_storage() -> dict[str, dict[str, str]]:
    path = _get_session_storage_path()
    if not isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as reader:
            value = load(reader)
        if isinstance(value, dict):
            return value
    except Exception as e:
        warning("读取 sessionStorage 失败：%s" % e)
    return {}


def _save_session_storage(origin: str, items: dict[str, str]):
    storage = _load_session_storage()
    storage[origin] = items
    with open(_get_session_storage_path(), "w", encoding="utf-8") as writer:
        dump(storage, writer, ensure_ascii=False, indent=4, sort_keys=True)


def _session_storage_script() -> str:
    storage_json = dumps(_load_session_storage(), ensure_ascii=False)
    return """
(() => {
    const storage = %s;
    const items = storage[window.location.origin];
    if (!items) return;
    for (const [key, value] of Object.entries(items)) {
        window.sessionStorage.setItem(key, value);
    }
})();
""" % storage_json


def restore_session_storage(context: Any):
    context.add_init_script(script=_session_storage_script())


def save_context_storage_state(context: Any):
    try:
        context.storage_state(path=get_storage_state_path(), indexed_db=True)
    except TypeError:
        context.storage_state(path=get_storage_state_path())


async def save_context_storage_state_async(context: Any):
    try:
        await context.storage_state(path=get_storage_state_path(), indexed_db=True)
    except TypeError:
        await context.storage_state(path=get_storage_state_path())


async def restore_session_storage_async(context: Any):
    await context.add_init_script(script=_session_storage_script())


def save_browser_state(page: Any):
    save_context_storage_state(page.context)
    session_storage = page.evaluate("""() => {
        const items = {};
        for (let i = 0; i < window.sessionStorage.length; i++) {
            const key = window.sessionStorage.key(i);
            items[key] = window.sessionStorage.getItem(key);
        }
        return { origin: window.location.origin, items };
    }""")
    if isinstance(session_storage, dict):
        origin = session_storage.get("origin")
        items = session_storage.get("items")
        if isinstance(origin, str) and isinstance(items, dict):
            _save_session_storage(origin, items)
            debug("已保存登录 sessionStorage")


async def save_browser_state_async(page: Any):
    await save_context_storage_state_async(page.context)
    session_storage = await page.evaluate("""() => {
        const items = {};
        for (let i = 0; i < window.sessionStorage.length; i++) {
            const key = window.sessionStorage.key(i);
            items[key] = window.sessionStorage.getItem(key);
        }
        return { origin: window.location.origin, items };
    }""")
    if isinstance(session_storage, dict):
        origin = session_storage.get("origin")
        items = session_storage.get("items")
        if isinstance(origin, str) and isinstance(items, dict):
            _save_session_storage(origin, items)
            debug("已保存登录 sessionStorage")
