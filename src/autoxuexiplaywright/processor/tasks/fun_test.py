"""Operations to finish fun test."""

import re as _re
from semver import Version as _Version
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
from autoxuexiplaywright.processor.tasks.test import TestTask as _TestTask
from autoxuexiplaywright.processor.tasks.utils import first_task as _first_task
from autoxuexiplaywright.processor.tasks.utils import clean_string as _clean_string


_logger = _get_logger(__name__)


@_module(_Version.parse(_version))
@_final
class FunTestTask(_TestTask):
    """Operations to finish fun test."""

    _POINTS_PAGE = "https://pc.xuexi.cn/points/my-points.html"
    _POINTS_CARDS = "div.my-points-card"
    _CARD_TITLE = "p.my-points-card-title"
    _CARD_ACTION = 'button, a, [role="button"]'
    _START_ACTION = 'button, a, [role="button"], div.button'
    _START_ACTION_TEXT = _re.compile("开始|继续|去答题|进入|挑战|答题")

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
        return ["趣味答题"]

    @_override
    async def _handle(self, page: _Page, task_name: str) -> bool:
        _ = await page.goto(self._POINTS_PAGE)
        await self.__wait_for_page_ready(page)
        cards = page.locator(self._POINTS_CARDS)
        await cards.last.wait_for()
        for i in range(await cards.count()):
            card = cards.nth(i)
            title = _clean_string(await card.locator(self._CARD_TITLE).inner_text())
            if title in self.handles:
                _logger.info(__("Processing fun test..."))
                action = card.locator(self._CARD_ACTION).last
                try:
                    async with page.context.expect_page(timeout=3000) as event:
                        if await action.count() > 0:
                            await action.click()
                        else:
                            await card.click()
                    test_page = await event.value
                except _TimeoutError:
                    test_page = page
                await self.__wait_for_page_ready(test_page)
                test_page = await self.__enter_test_page(test_page)
                if not await self.__is_test_page(test_page, 15000):
                    _logger.error(__("No fun test question page can be found."))
                    return False
                return await self._test(test_page)
        _logger.error(__("No fun test entrance can be found."))
        return False

    async def __enter_test_page(self, page: _Page) -> _Page:
        for _ in range(3):
            await self.__wait_for_page_ready(page)
            if await self.__is_test_page(page, 1000):
                return page
            action = page.locator(self._START_ACTION).filter(
                has_text=self._START_ACTION_TEXT,
            )
            if await action.count() == 0:
                return page
            try:
                async with page.context.expect_page(timeout=3000) as event:
                    await action.first.click()
                page = await event.value
            except _TimeoutError:
                await page.wait_for_load_state()
        return page

    async def __is_test_page(self, page: _Page, timeout: int) -> bool:
        ready = page.locator(f"{self._DETAIL_BODY}, {self._RESULT}").first
        try:
            await ready.wait_for(timeout=timeout)
        except _TimeoutError:
            return False
        return True

    async def __wait_for_page_ready(self, page: _Page):
        await page.wait_for_load_state()
        loading = page.locator(self._LOADING_SELECTOR)
        if await loading.count() > 0:
            try:
                await loading.last.wait_for(state="hidden", timeout=10000)
            except _TimeoutError:
                pass
