"""Operations to emulate watching video."""

from semver import Version as _Version
from typing import ClassVar as _ClassVar
from typing import final as _final
from typing import override as _override
from logging import getLogger as _get_logger
from urllib.parse import urljoin as _urljoin
from autoxuexiplaywright import APPAUTHOR as _APPAUTHOR
from autoxuexiplaywright import __version__ as _version
from playwright.async_api import Page as _Page
from playwright.async_api import Locator as _Locator
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
    _VIDEO_LINK_ATTRIBUTE = "data-link-target"
    _VIDEO_DETAIL_URL_MARKER = "/lgpage/detail/"
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
                state="attached",
                timeout=self._VIDEO_CONTENT_TIMEOUT_MSECS,
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

    @classmethod
    def _is_video_detail_target(cls, target: str) -> bool:
        """Return whether a card target is the current video-detail route."""
        return cls._VIDEO_DETAIL_URL_MARKER in target

    @classmethod
    def _is_static_article_target(cls, target: str) -> bool:
        """Return whether a card target is a static article rather than media."""
        target_path = target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]
        return (
            not cls._is_video_detail_target(target)
            and target_path.rstrip("/").endswith(".html")
        )

    async def _get_video_candidates(
        self,
        video_list: _Locator,
    ) -> list[tuple[_Locator, str, str]]:
        """Return unread playable cards, preferring real video detail links."""
        detail_cards: list[tuple[_Locator, str, str]] = []
        fallback_cards: list[tuple[_Locator, str, str]] = []
        for i in range(await video_list.count()):
            video = video_list.nth(i)
            title = _clean_string(await video.inner_text())
            if _has_read("video", title) or title in self._unavailable_video_titles:
                continue
            target = await video.get_attribute(self._VIDEO_LINK_ATTRIBUTE) or ""
            candidate = (video, title, target)
            if self._is_video_detail_target(target):
                detail_cards.append(candidate)
            elif self._is_static_article_target(target):
                _logger.debug(
                    "Skipping static article card in video list: title=%r target=%s",
                    title,
                    target,
                )
            else:
                fallback_cards.append(candidate)
        return [*detail_cards, *fallback_cards]

    async def _open_video_page(
        self,
        source_page: _Page,
        card: _Locator,
        target: str,
    ) -> _Page:
        """Open a video detail URL directly, falling back to the card click."""
        if self._VIDEO_DETAIL_URL_MARKER in target:
            video_page = await source_page.context.new_page()
            try:
                detail_url = _urljoin(source_page.url, target)
                _logger.info("Opening video detail page directly: %s", detail_url)
                await _goto(video_page, detail_url)
                return video_page
            except Exception as e:
                _logger.warning(
                    "Direct video detail navigation failed; using card click: %s",
                    e,
                )
                await video_page.close()

        async with source_page.context.expect_page() as e:
            await card.click()
        return await e.value

    async def _open_video_library(self, entrance_page: _Page) -> _Page:
        """Open the legacy library route when station cards are unavailable."""
        try:
            async with entrance_page.context.expect_page(timeout=20_000) as e:
                await entrance_page.locator(self._VIDEO_LIBRARY).click()
            return await e.value
        except _TimeoutError:
            # Some layouts update the station page instead of opening a tab.
            return entrance_page

    @_override
    async def _handle(self, page: _Page, task_name: str) -> bool:
        self._unavailable_video_titles.clear()
        await _goto(page, self._MAIN_PAGE)

        async with page.context.expect_page() as e:
            await page.locator(self._VIDEO_ENTRANCE).click()
        entrance_page = await e.value

        # Station cards already contain direct detail URLs. In headless Chromium
        # the dynamic library route can return lgdata 403 responses, while the
        # detail page and its HLS media requests load and play normally.
        library_page = entrance_page
        text_wrappers = library_page.locator(self._VIDEO_TEXT_WRAPPER)
        try:
            await text_wrappers.last.wait_for(state="attached", timeout=20_000)
        except _TimeoutError:
            library_page = await self._open_video_library(entrance_page)
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

            for text_wrapper, text, target in await self._get_video_candidates(
                text_wrappers,
            ):
                _logger.info(__("Processing video %(title)s"), {"title": text})
                video_page = None
                try:
                    video_page = await self._open_video_page(
                        library_page,
                        text_wrapper,
                        target,
                    )
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
