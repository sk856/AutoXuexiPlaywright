"""Reliable page navigation helpers."""

from asyncio import sleep as _sleep
from logging import getLogger as _get_logger
from playwright.async_api import Page as _Page


_logger = _get_logger(__name__)


async def goto(
    page: _Page,
    url: str,
    retries: int = 3,
    timeout_msecs: float = 45000,
) -> None:
    """Navigate to a page and retry transient browser/network interruptions."""
    last_error: Exception | None = None
    target_url = url.rstrip("/")
    for attempt in range(1, retries + 1):
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=timeout_msecs,
            )
            return
        except Exception as e:
            last_error = e
            current_url = page.url.rstrip("/")
            if current_url == target_url or current_url.startswith(target_url):
                try:
                    await page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=min(10000, timeout_msecs),
                    )
                    return
                except Exception as state_error:
                    _logger.debug(
                        "Target URL was reached but load-state wait failed: %s",
                        state_error,
                    )
            _logger.warning(
                "Navigation to %s was interrupted; retrying (%d/%d): %s",
                url,
                attempt,
                retries,
                e,
            )
            if attempt < retries:
                await _sleep(attempt * 1.5)
    if last_error is not None:
        raise last_error
