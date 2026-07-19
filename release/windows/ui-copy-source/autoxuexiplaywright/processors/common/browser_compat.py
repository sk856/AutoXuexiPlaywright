"""Browser settings shared by sync and async headless runners."""

from __future__ import annotations

from typing import Any


_CHROMIUM_HEADLESS_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--window-size=1440,1000",
)

# Some browser widgets compare the JavaScript-visible environment with a normal
# Chrome window. Chromium headless exposes automation-only values by default,
# even when the page itself otherwise works correctly.
HEADLESS_BROWSER_COMPATIBILITY_SCRIPT = r"""
(() => {
    const defineGetter = (object, key, getter) => {
        try {
            Object.defineProperty(object, key, {
                get: getter,
                configurable: true,
            });
        } catch (_) {}
    };

    defineGetter(Navigator.prototype, "webdriver", () => undefined);

    if (!window.chrome) {
        try {
            Object.defineProperty(window, "chrome", {
                value: {},
                configurable: true,
            });
        } catch (_) {}
    }
    if (window.chrome && !window.chrome.runtime) {
        try {
            Object.defineProperty(window.chrome, "runtime", {
                value: {},
                configurable: true,
            });
        } catch (_) {}
    }

    defineGetter(window, "outerWidth", () => window.innerWidth + 16);
    defineGetter(window, "outerHeight", () => window.innerHeight + 88);

    const originalQuery = navigator.permissions
        && navigator.permissions.query
        && navigator.permissions.query.bind(navigator.permissions);
    if (originalQuery) {
        navigator.permissions.query = (parameters) => {
            if (parameters && parameters.name === "notifications") {
                return Promise.resolve({
                    state: Notification.permission,
                    onchange: null,
                });
            }
            return originalQuery(parameters);
        };
    }
})();
"""


def headless_launch_options(browser_id: str) -> dict[str, Any]:
    """Return launch additions that keep Chromium headless page-compatible."""
    options: dict[str, Any] = {"args": ["--mute-audio"]}
    if browser_id == "chromium":
        options["args"].extend(_CHROMIUM_HEADLESS_ARGS)
        options["ignore_default_args"] = ["--enable-automation"]
    return options


def headless_context_options(
    browser_id: str, browser_version: str,
) -> dict[str, Any]:
    """Return context values consistent with the installed Chromium build."""
    if browser_id != "chromium":
        return {}
    version = str(browser_version).strip()
    if not version:
        return {}
    return {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version} Safari/537.36"
        ),
        "locale": "zh-CN",
        "viewport": {"width": 1440, "height": 1000},
    }
