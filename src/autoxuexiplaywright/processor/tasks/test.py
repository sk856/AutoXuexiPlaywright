"""Basic operations to emulate testing."""

from re import sub as _sub
from abc import ABCMeta as _ABCMeta
from random import uniform as _random_uniform
from typing import final as _final
from logging import getLogger as _get_logger
from contextlib import suppress as _suppress
from collections.abc import Iterator as _Iterator
from collections.abc import AsyncIterator as _AsyncIterator
from playwright.async_api import Page as _Page
from playwright.async_api import Locator as _Locator
from playwright.async_api import TimeoutError as _TimeoutError
from playwright.async_api import expect as _expect
from autoxuexiplaywright.sdk import Task as _Task
from autoxuexiplaywright.sdk import AnswerSource as _AnswerSource
from autoxuexiplaywright.sdk import CaptchaHandler as _CaptchaHandler
from autoxuexiplaywright.sdk import (
    RecordSupportedAnswerSource as _RecordSupportedAnswerSource,
)
from autoxuexiplaywright.module import iter_module_type as _iter_modules
from autoxuexiplaywright.localize import gettext as __
from autoxuexiplaywright.processor.tasks.utils import clean_string as _clean_string


_logger = _get_logger(__name__)


def _normalize_answer_text(text: str) -> str:
    return _clean_string(_sub(r"^[A-ZＡ-Ｚa-zａ-ｚ]\s*[.．、:：]\s*", "", text))  # noqa: RUF001


def _choice_index_from_answer(answer: str) -> int | None:
    normalized = _clean_string(answer).strip().upper()
    normalized = normalized.strip("()[]\uff08\uff09\u3010\u3011")
    normalized = _sub(r"\s+", "", normalized)
    normalized = _sub(r"[.\uFF0E\u3001:\uFF1A\u3002]+$", "", normalized)
    if len(normalized) != 1:
        return None
    if "A" <= normalized <= "Z":
        return ord(normalized) - ord("A")
    if "\uff21" <= normalized <= "\uff3a":
        return ord(normalized) - ord("\uff21")
    return None


class TestTask(_Task, metaclass=_ABCMeta):
    """Basic operations to emulate testing."""

    _DETAIL_BODY = "div.detail-body"
    _QUESTION = "div.question"
    _ACTION_ROW = "div.action-row"
    _TIPS = "div.line-feed"
    _RED_FONTS = 'font[color="red"]'
    _TIPS_BUTTON = "span.tips"
    _CHOICES = "div.q-answer.choosable, div.fill-answer.fill-answer-hover"
    _QUESTION_TITLE = "div.q-body"
    _BLANKS = (
        "div.q-body input, div.q-body textarea, input.blank, input.ant-input, "
        "input[type='text'], input:not([type]), textarea, [contenteditable='true']"
    )
    _RESULT = "div.practice-result"
    _RESULT_MODAL = "div.ant-modal-wrap"
    _ANALYSIS_CHOICE = "div.q-answer-analysis"
    _SOLUTION = "div.solution"
    _NEXT_BUTTON = "button.next-btn"
    _SUBMIT_BUTTON = "button.submit-btn"
    _PAGER = "div.pager"
    _CURRENT_POSITION = "span.big"
    _CAPTCHA = (
        "div#swiper_valid, div#JS_aliyun-captcha-dialog, div#JS_aliyun-captcha-main"
    )
    _CHOICE_TIMEOUT_MSECS = 30000
    _ACTION_TIMEOUT_MSECS = 30000
    _BLANK_TIMEOUT_MSECS = 5000
    _CONTROL_WAIT_TIMEOUT_MSECS = 10000
    _CAPTCHA_WAIT_TIMEOUT_MSECS = 3000
    _CAPTCHA_PROBE_TIMEOUT_MSECS = 800
    _TRANSITION_WAIT_TIMEOUT_MSECS = 10000
    _STATE_POLL_INTERVAL_MSECS = 100
    _DO_ANSWER_SLEEP_MIN_SECS = 10
    _DO_ANSWER_SLEEP_MAX_SECS = 15

    @_final
    async def _test(self, page: _Page) -> bool:  # noqa: PLR0912
        result = page.locator(self._RESULT)
        while await result.is_hidden() and not await self.__submitted_result_is_ready(
            page,
            result,
        ):
            detail_body = page.locator(self._DETAIL_BODY)
            await detail_body.wait_for()
            question = detail_body.locator(self._QUESTION)
            await _expect(question).to_be_visible()

            question_title = question.locator(self._QUESTION_TITLE)
            await _expect(question_title).to_be_visible()
            title = _clean_string(await question_title.inner_text())
            _logger.info(
                __("Question is: %(title)s"),
                {"title": title},
            )
            choices = question.locator(self._CHOICES)
            blanks = question.locator(self._BLANKS)
            controls = question.locator(f"{self._CHOICES}, {self._BLANKS}")
            try:
                await controls.first.wait_for(
                    state="attached",
                    timeout=self._CONTROL_WAIT_TIMEOUT_MSECS,
                )
            except _TimeoutError:
                _logger.error(__("Cannot find available answer controls."))
                return False

            tips_button = question.locator(self._TIPS_BUTTON)
            tips = page.locator(self._TIPS).last
            position = 0
            choices_count = await choices.count()
            blanks_count = await blanks.count()
            choice_titles: list[str] = []
            if choices_count > 0:
                choice_titles = [
                    _clean_string(c) for c in await choices.all_inner_texts()
                ]
            if len(choice_titles) > 0:
                _logger.info(
                    __("Available choices: %(choices)s"),
                    {"choices": choice_titles},
                )
            async for answer in self.__get_answer(
                title,
                choice_titles,
                tips_button,
                tips,
            ):
                if choices_count > 0 and not await self.__choice_item(choices, answer):
                    _logger.warning(
                        __("Failed to choice the item with answer %(answer)s"),
                        {"answer": answer},
                    )

                if blanks_count > 0:
                    if await self.__fill_blank(blanks, position, answer):
                        position += 1
                    else:
                        _logger.warning(
                            __(
                                "Failed to fill the blank at %(position)d with answer %(answer)s",  # noqa: E501
                            ),
                            {"position": position, "answer": answer},
                        )

            if choices_count == 0 and blanks_count == 0:
                _logger.warning(__("No answer elements found for current question."))

            action_row = detail_body.locator(self._ACTION_ROW)
            solution = detail_body.locator(self._SOLUTION)
            pager = page.locator(self._PAGER)
            total = int((await pager.inner_text()).split("/")[-1])
            current_position = pager.locator(self._CURRENT_POSITION)
            current = int(await current_position.inner_text())
            if not await self.__go_to_next_question_or_submit(
                title,
                choice_titles,
                action_row,
                solution,
            ):
                return False

            if current < total:
                _logger.debug(__("Still needs handling, continuing..."))
                await _expect(current_position).to_have_text(str(current + 1))
            else:
                _logger.info(__("Handle test completed."))
                await _expect(result).to_be_visible()

        return True

    @_final
    async def __submitted_result_is_ready(
        self,
        page: _Page,
        result: _Locator,
    ) -> bool:
        modal = page.locator(self._RESULT_MODAL)
        analysis = page.locator(self._ANALYSIS_CHOICE)
        modal_visible = await modal.count() > 0 and await modal.last.is_visible()
        if not modal_visible and await analysis.count() == 0:
            return False
        try:
            await result.last.wait_for(state="visible", timeout=20_000)
            return True
        except _TimeoutError as e:
            modal_text = ""
            if modal_visible:
                with _suppress(_TimeoutError):
                    modal_text = _clean_string(
                        await modal.last.inner_text(timeout=3000),
                    )
            _logger.warning(
                "Submitted question is covered by a result modal; "
                "stopping repeated answer clicks: text=%r error=%s",
                modal_text[:200],
                e,
            )
            return modal_visible and await analysis.count() > 0

    @_final
    async def __fill_blank(self, blanks: _Locator, position: int, answer: str) -> bool:
        try:
            await blanks.last.wait_for(
                state="attached",
                timeout=self._BLANK_TIMEOUT_MSECS,
            )
            if position < await blanks.count():
                _logger.debug(
                    __("Checking blank at %(position)d..."),
                    {"position": position},
                )
                blank = blanks.nth(position)
                _logger.debug(
                    __("Filling blank with answer %(answer)s..."),
                    {"answer": answer},
                )
                await blank.page.wait_for_timeout(self.__sleep_seconds * 1000)
                await blank.evaluate(
                    """
                    (element, value) => {
                        if ('value' in element) {
                            element.value = value;
                            element.setAttribute('value', value);
                        } else {
                            element.textContent = value;
                        }
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    """,
                    answer,
                    timeout=self._BLANK_TIMEOUT_MSECS,
                )
                return True
        except _TimeoutError as e:
            _logger.warning(__("Timed out while filling blank: %(e)s"), {"e": e})
            return False
        return False

    @_final
    async def __choice_item(self, choices: _Locator, answer: str) -> bool:
        await choices.last.wait_for()
        choices_count = await choices.count()
        choice_index = _choice_index_from_answer(answer)
        if choice_index is not None and choice_index < choices_count:
            _logger.debug(
                __("Choicing answer %(answer)s by option index %(position)d..."),
                {"answer": answer, "position": choice_index + 1},
            )
            return await self.__click_choice(choices.nth(choice_index))

        for position in range(choices_count):
            _logger.debug(
                __("Checking item at %(position)d..."),
                {"position": position},
            )
            choice = choices.nth(position)
            clean_answer = _normalize_answer_text(answer)
            if clean_answer == "":
                return False
            choice_text = _normalize_answer_text(await choice.inner_text())
            if clean_answer in choice_text or choice_text in clean_answer:
                _logger.debug(__("Choicing answer %(answer)s..."), {"answer": answer})
                return await self.__click_choice(choice)
        return False

    @_final
    async def __click_choice(self, choice: _Locator) -> bool:
        try:
            class_of_choice = (
                await choice.get_attribute(
                    "class",
                    timeout=self._CHOICE_TIMEOUT_MSECS,
                )
                or ""
            )
            if "q-answer-analysis" in class_of_choice:
                _logger.warning(
                    "Question is already submitted; skipping repeated choice click.",
                )
                return False
            if (
                "chosen" not in class_of_choice
                and "fill-answer-click" not in class_of_choice
            ):
                await choice.click(
                    delay=self.__sleep_seconds * 1000,
                    timeout=self._CHOICE_TIMEOUT_MSECS,
                )
            return True
        except _TimeoutError as e:
            _logger.warning(__("Timed out while choosing answer: %(e)s"), {"e": e})
            return False

    @_final
    async def __get_answer(  # noqa: PLR0912
        self,
        title: str,
        choice_titles: list[str],
        tips_button: _Locator,
        tips: _Locator,
    ) -> _AsyncIterator[str]:
        itered = False
        deferred_sources = []
        for source in _iter_modules(_AnswerSource):
            if source.__class__.__name__ == "OpenAICompatibleAnswerSource":
                deferred_sources.append(source)
                continue
            try:
                iterator = source.get_answer(title)
            except Exception as e:
                _logger.error(__("Failed to get answer because %(e)s"), {"e": e})
            else:
                source_itered = False
                async for answer in iterator:
                    yield answer
                    itered = True
                    source_itered = True
                if source_itered:
                    return

        if not itered:
            _logger.debug(
                __(
                    "No answer can be found from source, trying to get from page tips...",  # noqa: E501
                ),
            )
            class_of_tips_button = await tips_button.get_attribute("class") or ""
            tips_texts: list[str] = []
            if "ant-popover-open" not in class_of_tips_button:
                await tips_button.click()
                await tips.wait_for()
            red_fonts = tips.locator(self._RED_FONTS)
            if await red_fonts.count() > 0:
                await red_fonts.last.wait_for()
                for text in await red_fonts.all_inner_texts():
                    _logger.debug(__("Found tip %(tip)s."), {"tip": text})
                    tips_texts.append(_clean_string(text))
            class_of_tips_button = await tips_button.get_attribute("class") or ""
            if "ant-popover-open" in class_of_tips_button:
                await tips_button.click()
                await tips.wait_for(state="hidden")

            for text in self.__strip_answers(title, tips_texts, choice_titles):
                yield text
                itered = True
            if itered:
                return

        for source in deferred_sources:
            try:
                if source.__class__.__name__ == "OpenAICompatibleAnswerSource":
                    iterator = source.get_answer(
                        title,
                        blank=len(choice_titles) == 0,
                        choices=choice_titles,
                    )
                else:
                    iterator = source.get_answer(title)
            except Exception as e:
                _logger.error(__("Failed to get answer because %(e)s"), {"e": e})
            else:
                source_itered = False
                async for answer in iterator:
                    yield answer
                    source_itered = True
                if source_itered:
                    return

    @_final
    async def __go_to_next_question_or_submit(
        self,
        title: str,
        choice_titles: list[str],
        action_row: _Locator,
        solution: _Locator,
    ) -> bool:
        button = await self.__wait_for_action_button(action_row)
        if button is None:
            _logger.error(__("Cannot find available next button or submit button."))
            return False
        button_class = await button.get_attribute("class") or ""
        button_text = _clean_string(await button.inner_text())
        try:
            await button.click(
                delay=self.__sleep_seconds * 1000,
                timeout=self._ACTION_TIMEOUT_MSECS,
            )
        except _TimeoutError as e:
            _logger.error(
                __("Timed out while clicking next or submit: %(e)s"),
                {"e": e},
            )
            return False

        captcha_timeout_msecs = (
            self._CAPTCHA_WAIT_TIMEOUT_MSECS
            if "submit-btn" in button_class or "完成" in button_text
            else self._CAPTCHA_PROBE_TIMEOUT_MSECS
        )
        captcha = await self.__find_visible_captcha(
            action_row.page,
            captcha_timeout_msecs,
        )
        if captcha is not None and not await self.__handle_captcha(captcha):
            _logger.error(__("Failed to handle captcha"))
            return False

        if await self.__wait_for_solution_or_transition(title, solution):
            _logger.error(__("The answer to the question is wrong."))
            red_fonts = solution.locator(self._RED_FONTS)
            if await red_fonts.count() > 0:
                await red_fonts.last.wait_for()
                answers = [_clean_string(i) for i in await red_fonts.all_inner_texts()]
                await self.__update_answer(title, answers, choice_titles)
            next_button = await self.__wait_for_action_button(action_row)
            if next_button is None:
                _logger.error(__("Cannot find available next button."))
                return False
            await next_button.click(
                delay=self.__sleep_seconds * 1000,
                timeout=self._ACTION_TIMEOUT_MSECS,
            )
        return True

    @_final
    async def __wait_for_action_button(self, action_row: _Locator) -> _Locator | None:
        elapsed_msecs = 0
        while elapsed_msecs < self._ACTION_TIMEOUT_MSECS:
            for selector in (self._NEXT_BUTTON, self._SUBMIT_BUTTON):
                button = action_row.locator(selector).first
                try:
                    if await button.count() > 0 and await button.is_enabled(
                        timeout=self._STATE_POLL_INTERVAL_MSECS,
                    ):
                        return button
                except _TimeoutError:
                    pass
            await action_row.page.wait_for_timeout(self._STATE_POLL_INTERVAL_MSECS)
            elapsed_msecs += self._STATE_POLL_INTERVAL_MSECS
        return None

    @_final
    async def __find_visible_captcha(
        self,
        page: _Page,
        timeout_msecs: int,
    ) -> _Locator | None:
        captcha = page.locator(self._CAPTCHA)
        elapsed_msecs = 0
        while elapsed_msecs < timeout_msecs:
            for position in range(await captcha.count()):
                candidate = captcha.nth(position)
                if await candidate.is_visible():
                    return candidate
            await page.wait_for_timeout(self._STATE_POLL_INTERVAL_MSECS)
            elapsed_msecs += self._STATE_POLL_INTERVAL_MSECS
        return None

    @_final
    async def __wait_for_solution_or_transition(
        self,
        title: str,
        solution: _Locator,
    ) -> bool:
        page = solution.page
        question_title = page.locator(self._QUESTION_TITLE).first
        result = page.locator(self._RESULT).first
        elapsed_msecs = 0
        while elapsed_msecs < self._TRANSITION_WAIT_TIMEOUT_MSECS:
            if await solution.count() > 0 and await solution.first.is_visible():
                return True
            if await result.is_visible():
                return False
            if await question_title.count() > 0 and await question_title.is_visible():
                current_title = _clean_string(await question_title.inner_text())
                if current_title != title:
                    return False
            await page.wait_for_timeout(self._STATE_POLL_INTERVAL_MSECS)
            elapsed_msecs += self._STATE_POLL_INTERVAL_MSECS
        return False

    @_final
    async def __handle_captcha(self, captcha: _Locator) -> bool:
        for handler in _iter_modules(_CaptchaHandler):
            try:
                if await handler.solve(captcha):
                    return True
            except Exception as e:
                _logger.error(
                    __("Failed to handle captcha because %(e)s"),
                    {"e": e},
                )
        return False

    @_final
    async def __update_answer(
        self,
        title: str,
        answers: list[str],
        choice_titles: list[str],
    ):
        answers_to_record = list(self.__strip_answers(title, answers, choice_titles))

        for source in _iter_modules(_RecordSupportedAnswerSource):
            try:
                await source.record(title, answers_to_record)
            except Exception as e:
                _logger.error(__("Failed to record answer because %(e)s"), {"e": e})

    @_final
    def __strip_answers(
        self,
        title: str,
        answers: list[str],
        choice_titles: list[str],
    ) -> _Iterator[str]:
        judgement_size_match = len(answers) == 1 and len(choice_titles) == 2  # noqa: PLR2004
        judgement_content_match = all(
            any(content in title for title in choice_titles)
            for content in ["正确", "错误"]
        )
        if judgement_size_match and judgement_content_match:
            result = "正确" if answers[0] in title else "错误"
            _logger.warning(
                __("Rewriting judgement question result to %(result)s"),
                {"result": result},
            )
            yield result
            return

        _logger.debug(__("Yielding answers directly..."))
        yield from answers

    @property
    @_final
    def __sleep_seconds(self) -> float:
        return _random_uniform(  # noqa: S311
            self._DO_ANSWER_SLEEP_MIN_SECS,
            self._DO_ANSWER_SLEEP_MAX_SECS,
        )
