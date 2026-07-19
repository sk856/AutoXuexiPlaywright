from asyncio import sleep, to_thread
from time import monotonic
from re import sub
from random import randint, uniform
from queue import Empty, Queue
from urllib.parse import urlparse
from unicodedata import normalize as unicode_normalize
from m3u8 import loads
from playwright.async_api import Locator, TimeoutError
# Relative imports
from .task import Task, TaskStatus
from ..common import WAIT_RESULT_SECS, WAIT_CHOICE_SECS, ANSWER_SLEEP_MIN_SECS, ANSWER_SLEEP_MAX_SECS, VIDEO_REQUEST_REGEX, ANSWER_CONNECTOR, clean_string
from ..common.answer.utils import is_valid_answer, gen_random_string
from ..common.answer.sources import add_answer_to_all_sources, find_answer_in_answer_sources
from ..common.answer.ai import get_answer_from_ai
from ..common.captcha import (
    build_drag_positions,
    calculate_slider_max_distance,
    build_local_slider_payload,
    request_local_slider_distance,
)
from ..common.selectors import Selectors, PointsSelectors, TestSelectors
from ..common.urls import DAILY_EXAM_PAGE, WEEKLY_EXAM_PAGE, SPECIAL_EXAM_PAGE, POINTS_PAGE
from ...languages import get_language_string
from ...logger import info, debug, error, warning
from ...config import get_runtime_config
from ...events import EventID, find_event_by_id
from ...storage import get_cache_path


_ACTION_TIMEOUT_MSECS = int((WAIT_CHOICE_SECS + ANSWER_SLEEP_MAX_SECS + 5) * 1000)
_ACTION_ENABLE_TIMEOUT_MSECS = 5_000
_ACTION_CLICK_RETRIES = 3
_ACTION_CLICK_TIMEOUT_MSECS = 3_000
_CHOICE_CLICK_RETRIES = 3
_CHOICE_CLICK_TIMEOUT_MSECS = 4_000
_QUESTION_READY_TIMEOUT_MSECS = 20_000
_QUESTION_TRANSITION_TIMEOUT_MSECS = 20_000
_LOADING_TIMEOUT_MSECS = 10_000
_MAX_QUESTION_STEPS = 100
_MANUAL_ANSWER_TIMEOUT_SECS = 120
_FINAL_CAPTCHA_WAIT_MSECS = 15_000
_CAPTCHA_VERIFY_TIMEOUT_MSECS = 4_000


def _normalize_answer_text(text: str) -> str:
    return clean_string(sub(r"^[A-ZＡ-Ｚa-zａ-ｚ]\s*[.．、:：]\s*", "", text))


def _normalize_choice_text(text: str) -> str:
    """Normalize an answer/choice for matching without changing its meaning."""
    normalized = unicode_normalize("NFKC", _normalize_answer_text(text))
    normalized = normalized.strip("()[]【】")
    return sub(r"\s+", "", normalized).casefold()


def _choice_index_from_answer(answer: str) -> int | None:
    normalized = unicode_normalize("NFKC", clean_string(answer)).strip().upper()
    normalized = normalized.strip("()[]【】")
    normalized = sub(r"\s+", "", normalized)
    normalized = sub(r"[.．、:：。]+$", "", normalized)
    if len(normalized) != 1:
        return None
    if "A" <= normalized <= "Z":
        return ord(normalized) - ord("A")
    return None


def _choice_text_matches(answer: str, choice_text: str) -> bool:
    """Match answer text conservatively, especially for opposite short options."""
    if not answer or not choice_text:
        return False
    if answer == choice_text:
        return True

    if answer in choice_text:
        shorter, longer = answer, choice_text
    elif choice_text in answer:
        shorter, longer = choice_text, answer
    else:
        return False

    # Short options are commonly opposites: 能/不能、可以/不可以、正确/不正确.
    if len(shorter) < 2:
        return False

    negation_prefixes = ("不", "未", "无", "非", "没", "莫", "勿", "否", "not ", "no ", "non-", "in")
    if any(longer.startswith(prefix) and longer[len(prefix):] == shorter
           for prefix in negation_prefixes):
        return False
    return True


class _TestTask(Task):
    @property
    def requires(self) -> list[str]:
        return ["登录"]

    async def finish(self) -> bool:
        self._pending_answer_cache = None
        question_steps = 0
        while not await self._is_test_finished():
            question_steps += 1
            if question_steps > _MAX_QUESTION_STEPS:
                error("答题步骤超过上限，停止任务以避免循环卡住")
                return False

            question = self.last_page.locator(TestSelectors.QUESTION).last
            if not await self._wait_locator(
                    question, state="visible", timeout=_QUESTION_READY_TIMEOUT_MSECS):
                error("等待题目加载超时，当前页面：%s" % self.last_page.url)
                return False

            await question.scroll_into_view_if_needed()
            choices = question.locator(TestSelectors.ANSWERS)
            answer_items = choices.locator(TestSelectors.ANSWER_ITEM)
            blanks = question.locator(TestSelectors.BLANK)

            # The question shell/title can become visible before its choices or
            # blank inputs are mounted. Poll the actual answer controls instead
            # of treating the transient zero count as a terminal page error.
            answer_ready_deadline = (
                monotonic() + _QUESTION_READY_TIMEOUT_MSECS / 1000)
            while (await answer_items.count() <= 0 and await blanks.count() <= 0
                   and monotonic() < answer_ready_deadline):
                await self.last_page.wait_for_timeout(100)
            if await answer_items.count() <= 0 and await blanks.count() <= 0:
                warning(get_language_string("core-warning-no-answer-element"))
                return False

            title_element = question.locator(TestSelectors.QUESTION_TITLE).last
            await title_element.scroll_into_view_if_needed()
            title = clean_string(await title_element.inner_text())
            info(get_language_string("core-info-current-question-title") % title)
            tips = [title]
            if await answer_items.count() > 0:
                items_to_answer = answer_items
                blank = False
                tips.append(get_language_string("core-available-answers") +
                            ANSWER_CONNECTOR.join(
                    [clean_string(item) for item in await items_to_answer.all_inner_texts()]))
                debug(get_language_string(
                    "core-debug-current-question-type-choice"))
            elif await blanks.count() > 0:
                items_to_answer = blanks
                blank = True
                debug(get_language_string(
                    "core-debug-current-question-type-blank"))
            else:
                warning(get_language_string("core-warning-no-answer-element"))
                return False

            if not await self._do_answer(items_to_answer, blank, tips):
                error(get_language_string("core-error-answer-failed"))
            if not await self._go_to_next_question(title):
                self._pending_answer_cache = None
                return False
            if await self._is_test_finished():
                # A final result does not prove this individual answer was
                # accepted, so do not pollute the cache with it.
                self._pending_answer_cache = None
                return True
            if await self._has_solution_visible():
                self._pending_answer_cache = None
                error(get_language_string("core-error-answer-is-wrong") % title)
                if not await self._go_to_next_question(title):
                    return False
            else:
                self._commit_pending_answer_cache()
        return True

    async def _get_answer_from_page(self) -> list[str]:
        answer_on_page: list[str] = []
        question = self.last_page.locator(TestSelectors.QUESTION).last
        tips = question.locator(TestSelectors.TIPS).last
        try:
            if await tips.count() <= 0:
                return answer_on_page
            if "ant-popover-open" not in (await tips.get_attribute("class") or ""):
                await tips.click(timeout=_ACTION_TIMEOUT_MSECS)

            # The hint popover is rendered asynchronously. Counting it
            # immediately after click intermittently returns no visible node.
            deadline = monotonic() + WAIT_CHOICE_SECS
            visible_popover = None
            while monotonic() < deadline and visible_popover is None:
                popovers = self.last_page.locator(TestSelectors.POPOVER)
                for i in range(await popovers.count()):
                    candidate = popovers.nth(i)
                    try:
                        if await candidate.is_visible():
                            visible_popover = candidate
                            break
                    except Exception:
                        pass
                if visible_popover is None:
                    await self.last_page.wait_for_timeout(100)

            if visible_popover is not None:
                font = visible_popover.locator(TestSelectors.ANSWER_FONT)
                if await self._wait_locator(font.last, timeout=WAIT_CHOICE_SECS * 1000):
                    for answer in [clean_string(text) for text in await font.all_inner_texts()]:
                        if is_valid_answer(answer) and answer not in answer_on_page:
                            answer_on_page.append(answer)
        except TimeoutError as e:
            warning("读取题目提示超时：%s" % e)
        except Exception as e:
            warning("读取题目提示失败：%s" % e)
        finally:
            try:
                if await tips.count() > 0 and "ant-popover-open" in (await tips.get_attribute("class") or ""):
                    await tips.click(timeout=3000)
            except Exception:
                pass
        debug(get_language_string("core-debug-raw-answer-list") % answer_on_page)
        return answer_on_page

    async def _get_answer_from_manual_input(self, tips: list[str]) -> list[str]:
        if get_runtime_config().get_video:
            await self._get_video()
        queue: Queue[list[str]] = Queue(1)
        find_event_by_id(EventID.ANSWER_REQUESTED).invoke(
            "\n".join(tips), queue)
        try:
            return await to_thread(
                queue.get, True, _MANUAL_ANSWER_TIMEOUT_SECS)
        except Empty:
            warning("等待人工输入答案超时，将继续处理当前题目")
            return []

    async def _wait_for_enabled_action(self, action: Locator) -> bool:
        """Wait for the exam page to enable Next/Submit after an answer click."""
        deadline = monotonic() + _ACTION_ENABLE_TIMEOUT_MSECS / 1000
        while monotonic() < deadline:
            if await action.count() > 0:
                try:
                    await action.wait_for(state="visible", timeout=500)
                    if await action.is_enabled():
                        return True
                except TimeoutError:
                    pass
                except Exception:
                    pass
            await self.last_page.wait_for_timeout(100)
        return False

    async def _click_action_with_retry(self, selector: str) -> bool:
        """Click a React-rendered action button using a fresh locator per try."""
        for attempt in range(1, _ACTION_CLICK_RETRIES + 1):
            action = self.last_page.locator(TestSelectors.TEST_ACTION_ROW).locator(selector).last
            if not await self._wait_for_enabled_action(action):
                await self.last_page.wait_for_timeout(150)
                continue
            try:
                # Do not keep a locator across an artificial delay: React may
                # replace the button after the answer state is committed.
                action = self.last_page.locator(
                    TestSelectors.TEST_ACTION_ROW
                ).locator(selector).last
                await action.wait_for(state="visible", timeout=500)
                await action.click(timeout=_ACTION_CLICK_TIMEOUT_MSECS)
                return True
            except TimeoutError as exc:
                warning("点击答题操作按钮第 %s/%s 次失败，按钮可能正在刷新：%s" % (
                    attempt, _ACTION_CLICK_RETRIES, exc))
                # A native click is useful when only Playwright's stability
                # check loses a race with a React replacement. It still acts on
                # a freshly queried, visible/enabled element.
                try:
                    action = self.last_page.locator(
                        TestSelectors.TEST_ACTION_ROW
                    ).locator(selector).last
                    if await self._wait_for_enabled_action(action):
                        await action.evaluate("element => element.click()", timeout=1000)
                        return True
                except Exception:
                    pass
                await self.last_page.wait_for_timeout(200)
            except Exception as exc:
                warning("点击答题操作按钮第 %s/%s 次出现异常：%s" % (
                    attempt, _ACTION_CLICK_RETRIES, exc))
                await self.last_page.wait_for_timeout(200)
        return False

    async def _wait_for_action_or_transition(self, previous_title: str) -> tuple[str, str | None]:
        """Wait for an enabled action or for a React transition already in flight."""
        deadline = monotonic() + _QUESTION_TRANSITION_TIMEOUT_MSECS / 1000
        while monotonic() < deadline:
            if await self._is_test_finished():
                return "finished", None
            current_title = await self._current_question_title()
            if previous_title and current_title and current_title != previous_title:
                debug("检测到答题页面已切换到下一题：旧题目=%r，新题目=%r" %
                      (previous_title, current_title))
                return "transition", None

            for selector, action_name in (
                (TestSelectors.TEST_NEXT_QUESTION_BTN, "next"),
                (TestSelectors.TEST_SUBMIT_BTN, "submit"),
            ):
                action = self.last_page.locator(
                    TestSelectors.TEST_ACTION_ROW).locator(selector).last
                try:
                    if (await action.count() > 0 and await action.is_visible()
                            and await action.is_enabled()):
                        return "action", action_name
                except Exception:
                    pass
            await self.last_page.wait_for_timeout(100)
        return "timeout", None

    async def _go_to_next_question(self, previous_title: str | None = None) -> bool:
        if previous_title is None:
            previous_title = await self._current_question_title()
        had_solution = await self._has_solution_visible()
        submitted = False
        final_action = False
        try:
            wait_state, action_name = await self._wait_for_action_or_transition(
                previous_title or "")
            if wait_state in ("finished", "transition"):
                return True
            if wait_state != "action" or action_name is None:
                error("答题操作按钮存在但始终未启用：下一题/提交按钮可能正在刷新")
                return False

            selector = (
                TestSelectors.TEST_NEXT_QUESTION_BTN
                if action_name == "next" else TestSelectors.TEST_SUBMIT_BTN
            )
            action = self.last_page.locator(
                TestSelectors.TEST_ACTION_ROW).locator(selector).last
            try:
                action_text = clean_string(
                    await action.inner_text(timeout=1000)).replace(" ", "")
                final_action = action_name == "next" and "完成" in action_text
            except Exception:
                final_action = False

            if not await self._click_action_with_retry(selector):
                error(get_language_string("core-error-next-or-submit-timeout") %
                      ("下一题按钮在页面刷新期间无法点击"
                       if action_name == "next" else "提交按钮在页面刷新期间无法点击"))
                return False
            submitted = action_name == "submit"
        except TimeoutError as e:
            error(get_language_string("core-error-next-or-submit-timeout") % e)
            return False

        captcha_wait = (
            _FINAL_CAPTCHA_WAIT_MSECS if final_action
            else (5000 if submitted else 800)
        )
        if not await self._handle_captcha(captcha_wait):
            error(get_language_string("core-error-captcha-failed"))
            return False

        loading = self.last_page.locator(Selectors.LOADING)
        if await loading.count() > 0:
            debug(get_language_string("core-debug-found-loading"))
            try:
                await loading.wait_for(state="hidden", timeout=_LOADING_TIMEOUT_MSECS)
            except TimeoutError:
                warning("答题加载动画等待超时，将继续检查题目是否已经切换")

        return await self._wait_for_question_transition(
            previous_title or "", had_solution)

    async def _current_question_title(self) -> str:
        try:
            questions = self.last_page.locator(TestSelectors.QUESTION)
            if await questions.count() <= 0:
                return ""
            title = questions.last.locator(TestSelectors.QUESTION_TITLE).last
            return clean_string(await title.inner_text(timeout=2000))
        except Exception:
            return ""

    async def _has_solution_visible(self) -> bool:
        for selector in (TestSelectors.TEST_SOLUTION, TestSelectors.TEST_ANALYSIS_ANSWER):
            elements = self.last_page.locator(selector)
            for i in range(await elements.count()):
                try:
                    if await elements.nth(i).is_visible():
                        return True
                except Exception:
                    pass
        return False

    async def _wait_for_question_transition(
        self, previous_title: str, had_solution: bool,
    ) -> bool:
        deadline = monotonic() + _QUESTION_TRANSITION_TIMEOUT_MSECS / 1000
        while monotonic() < deadline:
            if await self._is_test_finished():
                return True
            current_title = await self._current_question_title()
            if previous_title and current_title and current_title != previous_title:
                return True
            if not had_solution and await self._has_solution_visible():
                return True
            await self.last_page.wait_for_timeout(100)

        # The page may finish replacing the question just after the polling
        # deadline (especially in headless mode). Re-read the DOM once before
        # declaring a failure so a completed transition is not lost.
        if await self._is_test_finished():
            return True
        final_title = await self._current_question_title()
        if previous_title and final_title and final_title != previous_title:
            debug("轮询结束时确认题目已切换：旧题目=%r，新题目=%r" %
                  (previous_title, final_title))
            return True
        error("点击下一题后页面未切换，停止任务以避免重复答同一题：%s" % previous_title)
        return False

    def _commit_pending_answer_cache(self) -> None:
        pending = getattr(self, "_pending_answer_cache", None)
        if pending is None:
            return
        title, answers = pending
        add_answer_to_all_sources(title, answers)
        debug("已验证答题成功，写入答案缓存：题目=%r，答案=%r" % (title, answers))
        self._pending_answer_cache = None

    async def _do_answer(self, elements: Locator, blank: bool, tips: list[str], title: str | None = None) -> bool:

        async def do_answer(answers: list[str]) -> bool:
            if len(answers) <= 0:
                return False
            answer_count = await elements.count()
            if answer_count <= 0:
                warning(get_language_string("core-warning-no-answer-element"))
                return False
            if blank and answer_count == 1 and len(answers) > 1:
                answers = [ANSWER_CONNECTOR.join(answers)]
            if len(answers) > answer_count:
                warning(get_language_string("core-warning-too-much-answers"))
                return False
            debug(get_language_string("core-debug-final-answer-list") % answers)

            if blank:
                handled = True
                for i, answer in enumerate(answers):
                    debug(get_language_string("core-debug-filling-blank"))
                    answer_handled = await self._fill_blank(elements.nth(i), answer)
                    if not answer_handled:
                        warning(get_language_string(
                            "core-warning-answer-not-matched") % answer)
                    handled = handled and answer_handled
                return handled

            choice_texts = [
                _normalize_choice_text(await elements.nth(i).inner_text())
                for i in range(answer_count)
            ]
            matched_indices: list[int] = []
            for raw_answer in answers:
                answer = _normalize_choice_text(raw_answer)
                choice_index = _choice_index_from_answer(raw_answer)
                if not answer and choice_index is None:
                    warning(get_language_string(
                        "core-warning-answer-not-matched") % raw_answer)
                    return False

                # Prefer exact answer text. A one-letter answer is only treated
                # as an option index when it is not itself an option's text.
                exact = [i for i, text in enumerate(choice_texts)
                         if answer and answer == text]
                if len(exact) == 1:
                    matched = exact[0]
                    match_kind = "文本精确匹配"
                else:
                    if choice_index is not None and choice_index < answer_count:
                        matched = choice_index
                        match_kind = "选项字母"
                    else:
                        fuzzy = [i for i, text in enumerate(choice_texts)
                                 if _choice_text_matches(answer, text)]
                        matched = fuzzy[0] if len(fuzzy) == 1 else None
                        match_kind = "唯一包含匹配"

                if matched is None:
                    warning("答案无法唯一匹配选项：原始=%r，清理后=%r，页面选项=%r" %
                            (raw_answer, answer, choice_texts))
                    warning(get_language_string(
                        "core-warning-answer-not-matched") % raw_answer)
                    return False
                debug("答案映射：原始=%r，清理后=%r，方式=%s，第%d项，页面选项=%r" %
                      (raw_answer, answer, match_kind, matched + 1, choice_texts[matched]))
                if matched not in matched_indices:
                    matched_indices.append(matched)

            ordering = await self._is_ordering_choice(elements)
            handled = True
            for index in matched_indices:
                choice = (
                    await self._find_ordering_choice(choice_texts[index])
                    if ordering else elements.nth(index)
                )
                if choice is None:
                    warning("排序题当前未找到未点击模块：第%d项，目标=%r" %
                            (index + 1, choice_texts[index]))
                    return False
                debug(get_language_string(
                    "core-debug-choosing-choice") % choice)
                handled = await self._chose_answer(choice) and handled
            return handled

        if title == None:
            title = tips[0]

        # The current page hint is the freshest source. Try it before the
        # local cache so an old/stale answer cannot override today's answer.
        answer_from_page = await self._get_answer_from_page()
        if await do_answer(answer_from_page):
            return True

        cached_answers = find_answer_in_answer_sources(title)
        if await do_answer(cached_answers):
            warning("网页提示未能直接匹配，使用本地答案缓存：%r" % cached_answers)
            return True

        error(get_language_string("core-error-no-answer-found"))
        tips.append(
            get_language_string("core-available-tips") +
            ANSWER_CONNECTOR.join(answer_from_page)
        )
        answers_from_ai = await to_thread(get_answer_from_ai, title, tips, blank)
        if await do_answer(answers_from_ai):
            self._pending_answer_cache = (title, list(answers_from_ai))
            return True
        if len(answers_from_ai) > 0:
            warning(get_language_string("core-warning-ai-answer-unusable") %
                    ANSWER_CONNECTOR.join(answers_from_ai))
        if not get_runtime_config().ai_answer_enabled:
            answers_from_manual_input = await self._get_answer_from_manual_input(tips)
            if await do_answer(answers_from_manual_input):
                self._pending_answer_cache = (title, list(answers_from_manual_input))
                return True
        else:
            warning("AI 答题已开启，本题未能自动操作页面，跳过人工输入等待")
        warning(get_language_string("core-warning-no-valid-answer"))
        if blank:
            for i in range(await elements.count()):
                await self._fill_blank(elements.nth(
                    i), gen_random_string())
        else:
            answer_count = await elements.count()
            if answer_count > 0:
                await self._chose_answer(elements.nth(
                    randint(0, answer_count - 1)))
        return False

    async def _find_visible_captcha(
        self, wait_timeout_msecs: int,
    ) -> Locator | None:
        deadline = monotonic() + max(0, wait_timeout_msecs) / 1000
        while True:
            candidates = self.last_page.locator(TestSelectors.TEST_CAPTCHA_SWIPER)
            for index in range(await candidates.count()):
                candidate = candidates.nth(index)
                try:
                    if await candidate.is_visible():
                        return candidate
                except Exception:
                    pass
            if monotonic() >= deadline:
                return None
            await self.last_page.wait_for_timeout(100)

    async def _wait_captcha_hidden(
        self, captcha: Locator, timeout_msecs: int = _CAPTCHA_VERIFY_TIMEOUT_MSECS,
    ) -> bool:
        try:
            await captcha.wait_for(state="hidden", timeout=timeout_msecs)
            return True
        except TimeoutError:
            try:
                return await captcha.is_hidden()
            except Exception:
                return True
        except Exception:
            # A successful callback can detach and replace the dialog.
            return True

    async def _handle_captcha(self, wait_timeout_msecs: int = 300) -> bool:
        try:
            captcha = await self._find_visible_captcha(wait_timeout_msecs)
        except Exception as captcha_error:
            warning("检查滑块验证码时出现异常：%s" % captcha_error)
            return True
        if captcha is None:
            return True

        warning(get_language_string("core-warning-captcha-found"))
        try:
            slider = captcha.locator(TestSelectors.TEST_CAPTCHA_SLIDER).first
            target = captcha.locator(TestSelectors.TEST_CAPTCHA_TARGET).first
            await slider.wait_for(state="visible", timeout=5000)
            await target.wait_for(state="visible", timeout=5000)
            slider_box = await slider.bounding_box()
            target_box = await target.bounding_box()
            if slider_box is None or target_box is None:
                warning("未能读取滑块按钮或轨道位置")
                return False

            max_distance = calculate_slider_max_distance(slider_box, target_box)
            debug(
                "滑块几何：按钮 %.1fx%.1f，轨道 %.1fx%.1f，可拖动 %.1f" % (
                    slider_box["width"], slider_box["height"],
                    target_box["width"], target_box["height"], max_distance,
                )
            )
            if max_distance <= 0:
                warning("滑块轨道可拖动距离无效")
                return False

            config = get_runtime_config()
            if config.captcha_local_enabled and config.captcha_local_url.strip():
                try:
                    image = await captcha.screenshot(type="png")
                    captcha_box = await captcha.bounding_box()
                    payload = build_local_slider_payload(
                        image,
                        None if captcha_box is None else captcha_box["width"],
                        None if captcha_box is None else captcha_box["height"],
                        self.last_page.url,
                    )
                    info("正在调用本地滑块接口：%s" % config.captcha_local_url)
                    distance, confidence = await to_thread(
                        request_local_slider_distance,
                        config.captcha_local_url, payload,
                        config.captcha_local_token,
                        config.captcha_local_timeout_secs,
                    )
                    if distance is not None:
                        confidence_text = (
                            "未知" if confidence is None else "%.3f" % confidence)
                        info("本地滑块接口返回距离 %.1f，置信度 %s" %
                             (distance, confidence_text))
                        if await self._drag_captcha_by_distance(
                                captcha, slider_box, target_box, distance):
                            return True
                        warning("本地识别距离拖动后验证码仍然可见，将使用轨道终点拖动")
                    else:
                        warning("本地滑块接口未返回有效距离，将使用轨道终点拖动")
                except Exception as local_error:
                    warning("本地滑块识别失败：%s；将使用轨道终点拖动" % local_error)

            info("正在使用内置滑块轨道终点拖动")
            for attempt in range(3):
                slider = captcha.locator(TestSelectors.TEST_CAPTCHA_SLIDER).first
                target = captcha.locator(TestSelectors.TEST_CAPTCHA_TARGET).first
                slider_box = await slider.bounding_box()
                target_box = await target.bounding_box()
                if slider_box is None or target_box is None:
                    if await self._wait_captcha_hidden(captcha, 500):
                        return True
                    warning("第 %d 次拖动前未能刷新滑块坐标" % (attempt + 1))
                    continue
                distance = calculate_slider_max_distance(slider_box, target_box)
                if distance > 0 and await self._drag_captcha_by_distance(
                        captcha, slider_box, target_box, distance):
                    return True
                warning("第 %d 次内置滑块拖动未通过" % (attempt + 1))
                await self.last_page.wait_for_timeout(500)
            return await self._wait_captcha_hidden(captcha, 500)
        except Exception as captcha_error:
            warning("滑块验证码处理失败：%s" % captcha_error)
            return False

    async def _drag_captcha_by_distance(
        self, captcha: Locator, slider_box: dict, target_box: dict,
        distance: float,
    ) -> bool:
        max_distance = calculate_slider_max_distance(slider_box, target_box)
        distance = max(0.0, min(float(distance), max_distance))
        if distance <= 0:
            return False
        start_x = slider_box["x"] + slider_box["width"] / 2
        start_y = slider_box["y"] + slider_box["height"] / 2
        await self.last_page.mouse.move(start_x, start_y)
        await sleep(0.18)
        await self.last_page.mouse.down()
        try:
            await sleep(0.22)
            for index, (x, y) in enumerate(build_drag_positions(
                    start_x, start_y, distance, steps=58), start=1):
                await self.last_page.mouse.move(x, y, steps=1)
                await sleep(0.014 if index < 45 else 0.022)
            await sleep(0.57)
        finally:
            await self.last_page.mouse.up()
        return await self._wait_captcha_hidden(captcha)

    async def _get_video(self):
        video_player = self.last_page.locator(TestSelectors.TEST_VIDEO_PLAYER)
        if await video_player.count() > 0:
            # The count should always be 1...
            for i in range(await video_player.count()):
                await video_player.nth(i).hover()
                try:
                    async with self.last_page.expect_response(VIDEO_REQUEST_REGEX) as response:
                        await video_player.nth(i).locator(
                            TestSelectors.TEST_VIDEO_PLAY_BTN).click()
                except TimeoutError:
                    error(get_language_string(
                        "core-error-test-download-video-failed"))
                else:
                    if (await response.value).url.endswith(".mp4"):
                        info(get_language_string(
                            "core-info-test-download-video-success"))
                        with open(get_cache_path(str(i) + "video.mp4"), "wb") as writer:
                            writer.write(await (await response.value).body())
                    elif (await response.value).url.endswith(".m3u8"):
                        url = urlparse((await response.value).url)
                        prefix = "%s://%s" % (
                            url.scheme,
                            url.netloc + "/".join(url.path.split("/")[:-1])
                        )
                        m3u8_path = get_cache_path(str(i) + "video.m3u8")
                        try:
                            loads((await (await response.value).text()), prefix).dump(  # type: ignore
                                m3u8_path)
                            from ffmpeg.asyncio import FFmpeg  # type: ignore
                            ffmpeg = FFmpeg().option("y")  # type: ignore
                            ffmpeg = ffmpeg.input(m3u8_path)  # type: ignore
                            ffmpeg = ffmpeg.output(  # type: ignore
                                get_cache_path(str(i) + "video.mp4"), vcodec="copy")
                            await ffmpeg.execute()
                        except Exception as e:
                            debug(get_language_string(
                                "core-error-test-download-video-failed") + "：%s" % e)
                            error(get_language_string(
                                "core-error-test-download-video-failed"))
                    else:
                        error(get_language_string(
                            "core-error-test-download-video-failed"))

    async def _is_test_finished(self) -> bool:
        result = self.last_page.locator(TestSelectors.TEST_RESULT)
        for i in range(await result.count()):
            try:
                if await result.nth(i).is_visible():
                    return True
            except Exception:
                pass

        modal = self.last_page.locator(TestSelectors.TEST_RESULT_MODAL)
        for i in range(await modal.count()):
            try:
                if await modal.nth(i).is_visible():
                    modal_text = clean_string(await modal.nth(i).inner_text(timeout=2000))
                    warning("检测到答题结果遮罩层，停止继续点击：%s" % modal_text[:200])
                    return True
            except Exception:
                pass
        return False

    async def _is_ordering_choice(self, elements: Locator) -> bool:
        """Return whether the answer controls are click-to-order modules."""
        for i in range(await elements.count()):
            try:
                class_name = await elements.nth(i).get_attribute(
                    "class", timeout=1000) or ""
                if "fill-answer" in class_name:
                    return True
            except Exception:
                pass
        return False

    async def _find_ordering_choice(self, target_text: str) -> Locator | None:
        """Find an unselected ordering module by its current text.

        Ordering controls change from ``fill-answer-hover`` to
        ``fill-answer-click`` after selection, so the original nth(index) is
        not stable. Always query the current question again.
        """
        question = self.last_page.locator(TestSelectors.QUESTION).last
        candidates = question.locator("div.fill-answer")
        for i in range(await candidates.count()):
            candidate = candidates.nth(i)
            try:
                class_name = await candidate.get_attribute(
                    "class", timeout=1000) or ""
                if "fill-answer-click" in class_name:
                    continue
                choice_text = _normalize_choice_text(
                    await candidate.inner_text(timeout=1000))
                if choice_text == target_text:
                    return candidate
            except Exception:
                pass
        return None

    async def _fill_blank(self, blank: Locator, text: str) -> bool:
        try:
            await sleep(uniform(ANSWER_SLEEP_MIN_SECS, ANSWER_SLEEP_MAX_SECS))
            try:
                await blank.fill(text, timeout=WAIT_CHOICE_SECS * 1000)
            except Exception:
                await blank.evaluate(
                    """
                    (element, value) => {
                        const proto = element instanceof HTMLTextAreaElement
                            ? HTMLTextAreaElement.prototype
                            : HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                        if (setter) setter.call(element, value);
                        else if ('value' in element) element.value = value;
                        else element.textContent = value;
                        element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    """,
                    text,
                    timeout=WAIT_CHOICE_SECS * 1000,
                )
            return True
        except TimeoutError as e:
            warning(get_language_string("core-warning-fill-blank-timeout") % e)
            return False
        except Exception as e:
            warning("填写答案失败：%s" % e)
            return False

    async def _chose_answer(self, choice: Locator) -> bool:
        """Select one option without holding a stale DOM node during a delay."""
        for attempt in range(1, _CHOICE_CLICK_RETRIES + 1):
            try:
                class_name = await choice.get_attribute(
                    "class", timeout=_CHOICE_CLICK_TIMEOUT_MSECS) or ""
                if "q-answer-analysis" in class_name:
                    warning("题目已经提交并进入解析状态，不再重复点击选项")
                    return False
                if "chosen" in class_name or "fill-answer-click" in class_name:
                    return True

                if attempt == 1:
                    await self.last_page.wait_for_timeout(int(uniform(
                        ANSWER_SLEEP_MIN_SECS, ANSWER_SLEEP_MAX_SECS) * 1000))
                # Playwright's click delay used to hold the node for several
                # seconds, which made React detach it between mouse events.
                await choice.click(timeout=_CHOICE_CLICK_TIMEOUT_MSECS)
                return True
            except TimeoutError as e:
                warning("选择答案第 %s/%s 次失败，选项正在刷新：%s" % (
                    attempt, _CHOICE_CLICK_RETRIES, e))
                await self.last_page.wait_for_timeout(150)
            except Exception as e:
                warning("选择答案第 %s/%s 次出现异常：%s" % (
                    attempt, _CHOICE_CLICK_RETRIES, e))
                await self.last_page.wait_for_timeout(150)
        return False


class DailyTestTask(_TestTask):

    @property
    def handles(self) -> list[str]:
        return ["每日答题"]

    async def __aenter__(self):
        await self._goto(DAILY_EXAM_PAGE)
        info(get_language_string("core-info-processing-daily-test"))
        return self


class FunTestTask(_TestTask):

    @property
    def handles(self) -> list[str]:
        return ["趣味答题"]

    async def __aenter__(self):
        await self._goto(POINTS_PAGE)
        await self.last_page.locator(Selectors.LOADING).wait_for(
            state="hidden", timeout=WAIT_CHOICE_SECS * 1000)
        cards = self.last_page.locator(PointsSelectors.POINTS_CARDS)
        try:
            await cards.last.wait_for(timeout=WAIT_CHOICE_SECS * 1000)
        except TimeoutError as e:
            error(get_language_string("core-error-no-points-cards") % e)
            self.status = TaskStatus.FAILED
            return self
        for i in range(await cards.count()):
            card = cards.nth(i)
            title = clean_string(await card.locator(
                PointsSelectors.CARD_TITLE).first.inner_text())
            if title in self.handles:
                info(get_language_string("core-info-processing-fun-test"))
                action = card.locator(PointsSelectors.CARD_ACTION).last
                try:
                    async with self.last_page.context.expect_page(timeout=3000) as event:
                        if await action.count() > 0:
                            await action.click()
                        else:
                            await card.click()
                    self.pages.append(await event.value)
                except TimeoutError:
                    await self.last_page.wait_for_load_state()
                loading = self.last_page.locator(Selectors.LOADING)
                if await loading.count() > 0:
                    await loading.wait_for(state="hidden")
                return self
        error(get_language_string("core-error-no-available-fun-test"))
        self.status = TaskStatus.FAILED
        return self


class WeeklyTestTask(_TestTask):

    @property
    def handles(self) -> list[str]:
        return ["每周答题"]

    async def __aenter__(self):
        await self._goto(WEEKLY_EXAM_PAGE)
        await self.last_page.locator(Selectors.LOADING).wait_for(state="hidden")
        weeks = self.last_page.locator(TestSelectors.TEST_WEEKS)
        await weeks.last.wait_for()
        week = await self._get_first_available_week(weeks)
        while week == None:
            next_btn = self.last_page.locator(TestSelectors.TEST_NEXT_PAGE)
            warning(get_language_string("core-warning-no-test-on-current-page"))
            if (await next_btn.get_attribute("aria-disabled") or "") == "true":
                error(get_language_string("core-error-no-available-test"))
                self.status = TaskStatus.FAILED
                return self
            else:
                await next_btn.first.click()
                await self.last_page.locator(
                    Selectors.LOADING).wait_for(state="hidden")
                week = await self._get_first_available_week(weeks)
        title = clean_string(await week.locator(
            TestSelectors.TEST_WEEK_TITLE).inner_text())
        info(get_language_string("core-info-processing-weekly-test") % title)
        await week.locator(TestSelectors.TEST_BTN).click()
        return self

    async def _get_first_available_week(self, weeks: Locator) -> Locator | None:
        for i in range(await weeks.count()):
            week = weeks.nth(i)
            stat = await (week.locator(
                TestSelectors.TEST_WEEK_STAT).get_attribute("class")) or "done"
            if "done" not in stat:
                return week


class SpecialTestTask(_TestTask):

    @property
    def handles(self) -> list[str]:
        return ["专项答题"]

    async def __aenter__(self):
        await self._goto(SPECIAL_EXAM_PAGE)
        await self.last_page.locator(Selectors.LOADING).wait_for(state="hidden")
        items = self.last_page.locator(TestSelectors.TEST_ITEMS)
        await items.last.wait_for()
        item = await self._get_first_available_item(items)
        while item == None:
            next_btn = self.last_page.locator(TestSelectors.TEST_NEXT_PAGE)
            warning(get_language_string("core-warning-no-test-on-current-page"))
            if (await next_btn.get_attribute("aria-disabled") or "") == "true":
                error(get_language_string("core-error-no-available-test"))
                self.status = TaskStatus.FAILED
                return self
            else:
                await next_btn.first.click()
                await self.last_page.locator(
                    Selectors.LOADING).wait_for(state="hidden")
                item = await self._get_first_available_item(items)
        title_element = item.locator(TestSelectors.TEST_SPECIAL_TITLE)
        before_text = await title_element.locator(
            TestSelectors.TEST_SPECIAL_TITLE_BEFORE).inner_text()
        after_text = await title_element.locator(
            TestSelectors.TEST_SPECIAL_TITLE_AFTER).inner_text()
        title = clean_string((await title_element.inner_text()).removeprefix(
            before_text).removesuffix(after_text))
        info(get_language_string("core-info-processing-special-test") % title)
        await item.locator(TestSelectors.TEST_BTN).click()
        return self

    async def _get_first_available_item(self, items: Locator) -> Locator | None:
        for i in range(await items.count()):
            item = items.nth(i)
            if await item.locator(TestSelectors.TEST_SPECIAL_SOLUTION).count() == 0:
                return item
