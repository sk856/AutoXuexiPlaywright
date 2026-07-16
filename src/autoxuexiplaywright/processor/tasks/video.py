"""Operations to emulate watching video."""

from semver import Version as _Version
from typing import ClassVar as _ClassVar
from typing import final as _final
from typing import override as _override
from logging import getLogger as _get_logger
from autoxuexiplaywright import APPAUTHOR as _APPAUTHOR
from autoxuexiplaywright import __version__ as _version
from playwright.async_api import Page as _Page
from playwright.async_api import TimeoutError as _TimeoutError
from autoxuexiplaywright.sdk import Task as _Task
from autoxuexiplaywright.sdk import module_entrance as _module
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.processor.navigation import goto as _goto
from autoxuexiplaywright.processor.tasks.read import ReadTask as _ReadTask
from autoxuexiplaywright.processor.tasks.utils import first_task as _first_task
from autoxuexiplaywright.processor.tasks.utils import clean_string as _clean_string
from autoxuexiplaywright.processor.tasks.read_history import has_read as _has_read
from autoxuexiplaywright.processor.tasks.read_history import mark_read as _mark_read


_logger = _get_logger(__name__)


@_module(_Version.parse(_version))
@_final
class VideoTask(_ReadTask):
    """Operations to emulate watching video."""

    _VIDEO_ENTRANCE = 'div[data-data-id="tv-station-header"]>div.right>span.moreText'
    _VIDEO_LIBRARY = "div.more-wrap p.text"
    _VIDEO_TEXT_WRAPPER = "div.textWrapper"
    _VIDEO_CONTENT = "div.gr-video-player, video, audio"
    _VIDEO_CONTENT_TIMEOUT_MSECS = 20_000
    _unavailable_video_titles: _ClassVar[set[str]] = set()

    __requires = None

    @property
    @_override
    def name(self) -> str:
        return self.__class__.__name__

    @property
    @_override
    def author(self) -> str:
        return _APPAUTHOR

    @property
    @_override
    def requires(self) -> list[_Task]:
        if self.__requires is None:
            self.__requires = [_first_task("登录")]
        return self.__requires

    @property
    @_override
    def handles(self) -> list[str]:
        return ["视听学习", "视听学习时长", "我要视听学习"]

    async def _video_content_loaded(self, page: _Page, title: str) -> bool:
        try:
            await page.locator(self._VIDEO_CONTENT).first.wait_for(
                state="attached", timeout=self._VIDEO_CONTENT_TIMEOUT_MSECS,
            )
            return True
        except _TimeoutError as e:
            body_chars = 0
            try:
                body_text = await page.locator("body").inner_text(timeout=5000)
                body_chars = len(body_text.strip())
            except Exception as body_error:
                _logger.debug(
                    "Failed to inspect empty video page body: %s",
                    body_error,
                )
            _logger.error(
                "Video detail page did not load a playable element: "
                "title=%r url=%s body_chars=%d error=%s",
                title,
                page.url,
                body_chars,
                e,
            )
            return False

    @_override
    async def _handle(self, page: _Page, task_name: str) -> bool:
        await _goto(page, self._MAIN_PAGE)

        async with page.context.expect_page() as e:
            await page.locator(self._VIDEO_ENTRANCE).click()
        entrance_page = await e.value

        async with entrance_page.context.expect_page() as e:
            await entrance_page.locator(self._VIDEO_LIBRARY).click()
        library_page = await e.value

        text_wrappers = library_page.locator(self._VIDEO_TEXT_WRAPPER)
        while True:
            try:
                await text_wrappers.last.wait_for(
                    timeout=self._CHECK_ELEMENT_TIMEOUT_SECS * 1000,
                )
                await text_wrappers.last.wait_for(state="attached", timeout=5000)
            except _TimeoutError as e:
                _logger.error(
                    "Video library did not load: url=%s error=%s",
                    library_page.url,
                    e,
                )
                break

            for i in range(await text_wrappers.count()):
                text_wrapper = text_wrappers.nth(i)
                text = _clean_string(await text_wrapper.inner_text())
                if _has_read("video", text) or text in self._unavailable_video_titles:
                    continue

                _logger.info(__("Processing video %(title)s"), {"title": text})
                video_page = None
                try:
                    async with library_page.context.expect_page() as e:
                        await text_wrapper.click()
                    video_page = await e.value
                    if not await self._video_content_loaded(video_page, text):
                        self._unavailable_video_titles.add(text)
                        continue
                    if await self._read(video_page):
                        _mark_read("video", text)
                        return True
                    _logger.warning("Video reading did not complete: title=%r", text)
                    self._unavailable_video_titles.add(text)
                finally:
                    if video_page is not None and not video_page.is_closed():
                        await video_page.close()

            _logger.warning(
                __("No unread video on this page, trying next page..."),
            )
            if not await self._go_to_next_page(library_page):
                _logger.error(__("No video can be read."))
                break

        for opened_page in (library_page, entrance_page):
            if not opened_page.is_closed():
                await opened_page.close()
        return False
