from time import time, sleep
from playwright.sync_api import BrowserContext, Page, Locator, sync_playwright, TimeoutError
# Relative imports
from .task import do_task
from ..common import (
    TaskQueue, TaskStatus, WAIT_PAGE_SECS, tasks_to_be_done, scores,
    create_queues_from_existing_task_titles, set_task_status_by_task_title,
    wait_for_processing_resume,
)
from ..common.browser_compat import (
    HEADLESS_BROWSER_COMPATIBILITY_SCRIPT,
    headless_context_options,
    headless_launch_options,
)
from ..common.browser_state import get_storage_state_path, has_storage_state, restore_session_storage, save_context_storage_state
from ..common.selectors import PointsSelectors
from ..common.urls import POINTS_PAGE
from ...config import get_runtime_config
from ...languages import get_language_string
from ...events import EventID, find_event_by_id
from ...logger import info, error, warning, debug


_config = get_runtime_config()
_STATUS_CARD_TIMEOUT_MSECS = 5000
_VIDEO_TASK_TITLES = {"视听学习", "视听学习时长", "我要视听学习"}


def _goto_page(page: Page, url: str, retries: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return
        except Exception as exc:
            last_error = exc
            current_url = page.url.rstrip("/")
            target_url = url.rstrip("/")
            if current_url == target_url or current_url.startswith(target_url):
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return
                except Exception:
                    pass
            warning(f"页面导航中断，第 {attempt}/{retries} 次重试：{url}；{exc}")
            if attempt < retries:
                sleep(attempt * 1.5)
    if last_error is not None:
        raise last_error


def _is_card_finished(card: Locator) -> bool:
    progress_value = 0.0
    progress = card.locator(PointsSelectors.CARD_PROGRESS).first
    style = progress.get_attribute("style") or ""
    if style.startswith("width"):
        progress_percent = style.removeprefix(
            "width").replace(":", "").removesuffix(";").strip().removesuffix("%")
        try:
            progress_value = float(progress_percent) / 100
        except:
            warning(get_language_string(
                "core-warning-failed-to-parse-progress"))
    return progress_value == 1.0


def _get_status_from_page(page: Page, close: bool) -> bool:
    _goto_page(page, POINTS_PAGE)
    tasks_to_be_done.clear()

    points = page.locator(PointsSelectors.POINTS_SPAN)
    try:
        points.nth(0).wait_for()
        points.nth(1).wait_for()
        scores[0] = int(points.nth(0).inner_text())
        scores[1] = int(points.nth(1).inner_text())
    except:
        error(get_language_string("core-error-update-score-failed"))
    else:
        info(get_language_string("core-info-update-score-success") %
             tuple(scores))

    cards = page.locator(PointsSelectors.POINTS_CARDS)
    try:
        cards.last.wait_for(timeout=_STATUS_CARD_TIMEOUT_MSECS)
    except TimeoutError as e:
        error(get_language_string("core-error-no-points-cards") % e)
        if close and not page.is_closed():
            page.close()
        return True
    for i in range(cards.count()):
        card = cards.nth(i)
        title = card.locator(
            PointsSelectors.CARD_TITLE).first.inner_text().strip()
        if title in _config.skipped:
            if not set_task_status_by_task_title(title, TaskStatus.SKIPPED):
                warning(get_language_string(
                    "core-warning-failed-to-skip-task") % title)
        elif not _is_card_finished(card):
            if (title not in tasks_to_be_done):
                tasks_to_be_done.append(title)
    find_event_by_id(EventID.SCORE_UPDATED).invoke(tuple(scores))

    if close and not page.is_closed():
        page.close()
    return len(tasks_to_be_done) == 0



def _finish_video_task(
    playwright,
    main_context: BrowserContext,
    task_title: str,
    close: bool,
) -> bool:
    """Retry one video task in a temporary headed browser.

    Video details normally run in the main headless context. This temporary
    context is only used when direct detail navigation fails.
    """
    video_browser = None
    video_context = None
    try:
        video_browser = playwright[_config.browser_id].launch(
            headless=False,
            proxy=_config.proxy,
            channel=_config.browser_channel,
            executable_path=_config.executable_path,
            args=(
                [
                    "--mute-audio",
                    "--window-position=-32000,-32000",
                    "--window-size=1280,900",
                ]
                if _config.browser_id == "chromium"
                else ["--mute-audio"]
            ),
            devtools=False,
            firefox_user_prefs={"media.volume_scale": "0.0"},
        )
        video_context = video_browser.new_context(
            storage_state=main_context.storage_state(),
        )
        restore_session_storage(video_context)
        video_context.set_default_timeout(WAIT_PAGE_SECS * 1000)
        info("视频详情页无头读取失败，正在使用临时有头浏览器重试")
        result = do_task(video_context.new_page(), task_title, close)
        try:
            main_context.add_cookies(video_context.cookies())
        except Exception as e:
            debug("合并视频浏览器 Cookie 失败：%s" % e)
        return result
    except Exception as e:
        error("启动或执行视频专用有头浏览器失败：%s" % e)
        return False
    finally:
        if video_context is not None:
            for page in list(video_context.pages):
                if not page.is_closed():
                    page.close()
            video_context.close()
        if video_browser is not None:
            video_browser.close()


def _finish_queue(queue: TaskQueue, context: BrowserContext, playwright, close: bool):
    debug(get_language_string("core-debug-current-queue") %
          ", ".join([str(task) for task in queue]))
    results: list[bool] = []
    for task in queue:
        wait_for_processing_resume()
        if task in _VIDEO_TASK_TITLES:
            task_result = do_task(context.new_page(), task, close)
            if not task_result:
                warning("无头视频详情页读取失败，回退到临时有头浏览器")
                task_result = _finish_video_task(playwright, context, task, close)
        else:
            task_result = do_task(context.new_page(), task, close)
        debug(get_language_string("core-debug-task-result") %
              (str(task), str(task_result)))
        results.append(task_result)
    if not all(results):
        warning(get_language_string("core-warning-some-tasks-failed"))


def _finish_all(context: BrowserContext, playwright, close: bool = True):
    wait_for_processing_resume()
    do_task(context.new_page(), "登录", close)
    while True:
        wait_for_processing_resume()
        if _get_status_from_page(context.new_page(), close):
            break
        debug(get_language_string("core-debug-task-to-be-done-is") %
              str(tasks_to_be_done))
        queues = create_queues_from_existing_task_titles(*tasks_to_be_done)

        for queue in queues:
            _finish_queue(queue, context, playwright, close)

    if close:
        for page in context.pages:
            if not page.is_closed():
                page.close()


def start():
    start_time = time()
    with sync_playwright() as p:
        browser = p[_config.browser_id].launch(
            headless=True,
            proxy=_config.proxy,
            channel=_config.browser_channel,
            **headless_launch_options(_config.browser_id),
            devtools=False,
            firefox_user_prefs={"media.volume_scale": "0.0"},
            executable_path=_config.executable_path,
        )
        cookies_path = get_storage_state_path()
        context_options = headless_context_options(
            _config.browser_id, browser.version)
        if has_storage_state():
            context = browser.new_context(
                storage_state=cookies_path, **context_options)
        else:
            context = browser.new_context(**context_options)
        if _config.browser_id == "chromium":
            context.add_init_script(
                script=HEADLESS_BROWSER_COMPATIBILITY_SCRIPT)
        restore_session_storage(context)
        context.set_default_timeout(WAIT_PAGE_SECS*1000)
        try:
            _finish_all(context, p)
        except Exception as e:
            error(get_language_string("core-err-process-exception") % e)
        finally:
            save_context_storage_state(context)
            context.close()
            browser.close()
    delta_mins, delta_secs = divmod(time()-start_time, 60)
    delta_hrs, delta_mins = divmod(delta_mins, 60)
    finish_str = get_language_string("core-info-all-finished").format(
        int(delta_hrs), int(delta_mins), int(delta_secs))
    info(finish_str)
    find_event_by_id(EventID.FINISHED).invoke(finish_str)
