from time import time
from urllib.parse import urljoin, urlparse
from random import randint, uniform
from playwright.async_api import Locator, TimeoutError
# Relative imports
from .task import Task, TaskStatus
from ..common import (
    READ_TIME_SECS, READ_SLEEPS_MIN_SECS, READ_SLEEPS_MAX_SECS, clean_string,
    wait_for_processing_resume_async,
)
from ..common.read_history import has_read, mark_read
from ..common.selectors import Selectors, ReadSelectors
from ..common.urls import MAIN_PAGE
from ...languages import get_language_string
from ...logger import info, warning, error, debug


_READ_LIST_TIMEOUT_MSECS = 15000

_VIDEO_CONTENT_TIMEOUT_MSECS = 20000
_VIDEO_ELEMENT_VISIBILITY_TIMEOUT_MSECS = 1000
_VIDEO_ELEMENT_SCROLL_TIMEOUT_MSECS = 2000
_UNAVAILABLE_VIDEO_TITLES: set[str] = set()


def _is_static_article_target(target_url: str) -> bool:
    """Return whether a video-list card points to a static article page.

    The video library mixes real ``/lgpage/detail/`` cards with regular
    ``.html`` news articles.  The latter have no player and must not be
    selected as the fallback video candidate.
    """
    path = urlparse(target_url).path.lower()
    detail_marker = ReadSelectors.VIDEO_DETAIL_URL_MARKER.lower()
    return path.endswith(".html") and detail_marker not in target_url.lower()


class _ReadTask(Task):
    @property
    def requires(self) -> list[str]:
        return ["登录"]

    async def finish(self) -> bool:
        return await self._finish_reading_content()

    async def _finish_reading_content(self) -> bool:
        scroll_paragraphs_in_order = True
        scroll_video_subtitles_in_order = True
        start_time = time()
        deadline = start_time + READ_TIME_SECS
        while time() < deadline:
            await wait_for_processing_resume_async()
            remaining = deadline - time()
            delay = min(
                uniform(READ_SLEEPS_MIN_SECS, READ_SLEEPS_MAX_SECS),
                max(0.0, remaining),
            )
            if delay <= 0:
                break
            await self.last_page.wait_for_timeout(delay * 1000)
            try:
                player = self.last_page.locator(ReadSelectors.VIDEO_PLAYER)
                player_count = await player.count()
                if player_count > 0 and time() < deadline:
                    remaining_msecs = max(1, int((deadline - time()) * 1000))
                    await player.last.wait_for(timeout=min(5000, remaining_msecs))
                    for i in range(player_count):
                        if time() >= deadline:
                            break
                        current_player = player.nth(i)
                        try:
                            await current_player.wait_for(
                                state="visible",
                                timeout=min(
                                    _VIDEO_ELEMENT_VISIBILITY_TIMEOUT_MSECS,
                                    max(1, int((deadline - time()) * 1000)),
                                ),
                            )
                            if await current_player.locator(ReadSelectors.REPLAY_BTN).count() > 0:
                                continue
                            await current_player.hover(
                                timeout=min(
                                    _VIDEO_ELEMENT_SCROLL_TIMEOUT_MSECS,
                                    max(1, int((deadline - time()) * 1000)),
                                )
                            )
                            play_btn = current_player.locator(ReadSelectors.PLAY_BTN).first
                            if await play_btn.count() == 0:
                                continue
                            if "playing" not in (
                                await play_btn.get_attribute("class", timeout=1000) or ""
                            ):
                                await play_btn.click(
                                    timeout=min(
                                        _VIDEO_ELEMENT_SCROLL_TIMEOUT_MSECS,
                                        max(1, int((deadline - time()) * 1000)),
                                    )
                                )
                        except TimeoutError:
                            debug("视频播放器控件当前不可操作，跳过本轮")

                await self._scroll_elements(
                    self.last_page.locator(ReadSelectors.VIDEO_SUBTITLE),
                    scroll_video_subtitles_in_order,
                    deadline,
                )
                scroll_video_subtitles_in_order = False

                await self._scroll_elements(
                    self.last_page.locator(ReadSelectors.PAGE_PARAGRAPHS),
                    scroll_paragraphs_in_order,
                    deadline,
                )
                scroll_paragraphs_in_order = False
            except TimeoutError:
                debug("阅读页面元素操作超时，继续等待至阅读时限")
            except Exception as e:
                debug(get_language_string("core-debug-read-failed") % e)
                return False
        debug(f"阅读完成，实际用时 {time() - start_time:.1f} 秒")
        return True

    async def _mark_read_if_finished(self, kind: str, title: str) -> bool:
        result = await self._finish_reading_content()
        if result:
            mark_read(kind, title)
        return result

    async def _scroll_elements(self, elements: Locator, order: bool, deadline: float):
        count = await elements.count()
        if count <= 0:
            return
        for i in range(count):
            await wait_for_processing_resume_async()
            remaining = deadline - time()
            if remaining <= 0:
                break
            delay = min(
                uniform(READ_SLEEPS_MIN_SECS, READ_SLEEPS_MAX_SECS),
                remaining,
            )
            await self.last_page.wait_for_timeout(delay * 1000)
            remaining_msecs = max(1, int((deadline - time()) * 1000))
            if remaining_msecs <= 1:
                break
            index = i if order else randint(0, count - 1)
            element = elements.nth(index)
            try:
                # Subtitle containers can exist in the DOM before their text is
                # rendered, or remain hidden on videos without subtitles. Do
                # not let one such node stall the whole reading task.
                await element.wait_for(
                    state="visible",
                    timeout=min(_VIDEO_ELEMENT_VISIBILITY_TIMEOUT_MSECS, remaining_msecs),
                )
                await element.scroll_into_view_if_needed(
                    timeout=min(_VIDEO_ELEMENT_SCROLL_TIMEOUT_MSECS, remaining_msecs)
                )
            except TimeoutError:
                debug("阅读元素当前不可见，跳过本轮滚动")


class NewsTask(_ReadTask):

    @property
    def handles(self) -> list[str]:
        return ["我要选读文章"]

    async def __aenter__(self):
        await self._goto(MAIN_PAGE)
        title_span = self.last_page.locator(
            ReadSelectors.NEWS_TITLE_SPAN).first
        await title_span.wait_for()
        async with self.last_page.context.expect_page() as event:
            await title_span.click()
        self.pages.append(await event.value)
        news_list = self.last_page.locator(ReadSelectors.NEWS_LIST)
        if not await self._wait_locator(news_list.last, timeout=_READ_LIST_TIMEOUT_MSECS):
            # Some xuexi.cn cards now open an article directly instead of the article list.
            # In that case, keep the opened page and read it as the target article.
            if await self.last_page.locator(ReadSelectors.PAGE_PARAGRAPHS).count() > 0:
                news_title_text = clean_string(await self.last_page.title()) or self.last_page.url
                self._news_title_text = news_title_text
                info(get_language_string("core-info-processing-news") % news_title_text)
                return self
            error(get_language_string("core-error-no-available-news"))
            self.status = TaskStatus.FAILED
            return self
        news_title = await self._get_first_available_news_title(news_list)
        while news_title == None:
            next_btn = self.last_page.locator(ReadSelectors.NEXT_PAGE)
            warning(get_language_string("core-warning-no-news-on-current-page"))
            if await next_btn.count() == 0:
                # No more page(s) for news, mark task failed and end this function
                error(get_language_string("core-error-no-available-news"))
                self.status = TaskStatus.FAILED
                return self
            else:
                await next_btn.first.click()
                await self.last_page.locator(
                    Selectors.LOADING).wait_for(state="hidden")
                news_title = await self._get_first_available_news_title(news_list)
        news_title_text = clean_string(await news_title.inner_text())
        self._news_title_text = news_title_text
        info(get_language_string("core-info-processing-news") % news_title_text)
        async with self.last_page.context.expect_page() as event:
            await news_title.click()
        self.pages.append(await event.value)

        return self

    async def finish(self) -> bool:
        return await self._mark_read_if_finished("news", getattr(self, "_news_title_text", ""))

    async def _get_first_available_news_title(self, news_list: Locator) -> Locator | None:
        for i in range(await news_list.count()):
            news = news_list.nth(i)
            title_element = news.locator(ReadSelectors.NEWS_TITLE_TEXT)
            if not has_read("news", clean_string(await title_element.inner_text())):
                return title_element


class VideoTask(_ReadTask):

    @property
    def handles(self) -> list[str]:
        return ["视听学习", "视听学习时长", "我要视听学习"]

    async def __aenter__(self):
        await self._goto(MAIN_PAGE)
        async with self.last_page.context.expect_page() as event:
            await self.last_page.locator(ReadSelectors.VIDEO_ENTRANCE).first.click()
        self.pages.append(await event.value)

        # The TV-station page already contains video cards with data-link-target.
        # Going directly to the detail URL avoids the headless-only lgdata 403s
        # triggered by opening the dynamic "片库" route.
        text_wrappers = self.last_page.locator(ReadSelectors.VIDEO_TEXT_WRAPPER)
        if not await self._wait_locator(text_wrappers.last, timeout=_READ_LIST_TIMEOUT_MSECS):
            # Keep the old library route as a fallback for layouts that do not
            # expose cards on the TV-station page.
            video_library = self.last_page.locator(ReadSelectors.VIDEO_LIBRARY).first
            if await video_library.count() > 0:
                try:
                    async with self.last_page.context.expect_page() as event:
                        await video_library.click(timeout=_READ_LIST_TIMEOUT_MSECS)
                    self.pages.append(await event.value)
                    text_wrappers = self.last_page.locator(
                        ReadSelectors.VIDEO_TEXT_WRAPPER
                    )
                except Exception as e:
                    warning(f"打开视频片库失败，将继续检查当前页面：{e}")

        if not await self._wait_locator(text_wrappers.last, timeout=_READ_LIST_TIMEOUT_MSECS):
            if await self.last_page.locator(ReadSelectors.VIDEO_PLAYER).count() > 0 or await self.last_page.locator(ReadSelectors.PAGE_PARAGRAPHS).count() > 0:
                video_title_text = clean_string(await self.last_page.title()) or self.last_page.url
                self._video_title_text = video_title_text
                info(get_language_string("core-info-processing-video") % video_title_text)
                return self
            error(get_language_string("core-error-no-available-videos"))
            self.status = TaskStatus.FAILED
            return self

        text_wrapper = await self._get_first_available_video_title(text_wrappers)
        while text_wrapper == None:
            next_btn = self.last_page.locator(ReadSelectors.NEXT_PAGE)
            warning(get_language_string(
                "core-warning-no-videos-on-current-page"))
            if await next_btn.count() == 0:
                error(get_language_string("core-error-no-available-videos"))
                self.status = TaskStatus.FAILED
                return self
            else:
                await next_btn.first.click()
                await self.last_page.locator(
                    Selectors.LOADING).wait_for(state="hidden")
                text_wrapper = await self._get_first_available_video_title(
                    text_wrappers)

        video_title_text = clean_string(await text_wrapper.inner_text())
        self._video_title_text = video_title_text
        info(get_language_string("core-info-processing-video") %
             video_title_text)

        target_url = await text_wrapper.get_attribute(ReadSelectors.VIDEO_LINK_ATTRIBUTE)
        if target_url:
            target_url = urljoin(self.last_page.url, target_url)
            try:
                info(f"直接打开视频详情页：{target_url}")
                await self._goto(target_url)
            except Exception as e:
                warning(f"直接打开视频详情页失败，回退点击方式：{e}")
                async with self.last_page.context.expect_page() as event:
                    await text_wrapper.click()
                self.pages.append(await event.value)
        else:
            async with self.last_page.context.expect_page() as event:
                await text_wrapper.click()
            self.pages.append(await event.value)

        return self

    async def finish(self) -> bool:
        title = getattr(self, "_video_title_text", "")
        try:
            await self.last_page.locator("div.gr-video-player, video, audio").first.wait_for(
                state="attached", timeout=_VIDEO_CONTENT_TIMEOUT_MSECS
            )
        except TimeoutError as e:
            body_chars = 0
            try:
                body_chars = len((await self.last_page.locator("body").inner_text(timeout=5000)).strip())
            except Exception:
                pass
            error(
                f"视频详情页未加载播放器：标题={title!r}，URL={self.last_page.url}，"
                f"正文字符数={body_chars}，错误={e}"
            )
            _UNAVAILABLE_VIDEO_TITLES.add(title)
            return False
        return await self._mark_read_if_finished("video", title)

    async def _get_first_available_video_title(self, video_list: Locator) -> Locator | None:
        fallback: Locator | None = None
        for i in range(await video_list.count()):
            video = video_list.nth(i)
            title = clean_string(await video.inner_text())
            if title in _UNAVAILABLE_VIDEO_TITLES or has_read("video", title):
                continue
            target_url = await video.get_attribute(ReadSelectors.VIDEO_LINK_ATTRIBUTE) or ""
            if _is_static_article_target(target_url):
                debug(f"跳过视频列表中的静态文章卡片：标题={title!r}，URL={target_url}")
                continue
            # Prefer real detail cards over category/album links.
            if ReadSelectors.VIDEO_DETAIL_URL_MARKER in target_url:
                return video
            if fallback is None:
                fallback = video
        return fallback
