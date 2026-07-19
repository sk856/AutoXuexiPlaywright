from time import time
from asyncio import sleep
from asyncio import Task, TaskGroup, run
from playwright.async_api import BrowserContext, Page, Locator, Playwright, async_playwright, TimeoutError
# Relative imports
from .task import do_task
from ..common import (
    TaskQueue, TaskStatus, WAIT_PAGE_SECS, tasks_to_be_done, scores,
    create_queues_from_existing_task_titles, set_task_status_by_task_title,
    wait_for_processing_resume_async,
)
from ..common.browser_compat import (
    HEADLESS_BROWSER_COMPATIBILITY_SCRIPT,
    headless_context_options,
    headless_launch_options,
)
from ..common.browser_state import get_storage_state_path, has_storage_state, restore_session_storage_async, save_context_storage_state_async
from ..common.selectors import PointsSelectors
from ..common.urls import POINTS_PAGE
from ...config import get_runtime_config
from ...languages import get_language_string
from ...events import EventID, find_event_by_id
from ...logger import info, error, warning, debug


_config = get_runtime_config()
_STATUS_CARD_TIMEOUT_MSECS = 5000
_VIDEO_TASK_TITLES = {"视听学习", "视听学习时长", "我要视听学习"}


async def _goto_page(page: Page, url: str, retries: int = 3) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            return
        except Exception as exc:
            last_error = exc
            current_url = page.url.rstrip("/")
            target_url = url.rstrip("/")
            if current_url == target_url or current_url.startswith(target_url):
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return
                except Exception:
                    pass
            warning(f"页面导航中断，第 {attempt}/{retries} 次重试：{url}；{exc}")
            if attempt < retries:
                await sleep(attempt * 1.5)
    if last_error is not None:
        raise last_error


async def _is_card_finished(card: Locator) -> bool:
    progress_value = 0.0
    progress = card.locator(PointsSelectors.CARD_PROGRESS).first
    style = await progress.get_attribute("style") or ""
    if style.startswith("width"):
        progress_percent = style.removeprefix(
            "width").replace(":", "").removesuffix(";").strip().removesuffix("%")
        try:
            progress_value = float(progress_percent) / 100
        except:
            warning(get_language_string(
                "core-warning-failed-to-parse-progress"))
    return progress_value == 1.0


async def _get_status_from_page(page: Page, close: bool) -> bool:
    await _goto_page(page, POINTS_PAGE)
    tasks_to_be_done.clear()

    points = page.locator(PointsSelectors.POINTS_SPAN)
    try:
        await points.nth(0).wait_for()
        await points.nth(1).wait_for()
        scores[0] = int(await points.nth(0).inner_text())
        scores[1] = int(await points.nth(1).inner_text())
    except:
        error(get_language_string("core-error-update-score-failed"))
    else:
        info(get_language_string("core-info-update-score-success") %
             tuple(scores))

    cards = page.locator(PointsSelectors.POINTS_CARDS)
    try:
        await cards.last.wait_for(timeout=_STATUS_CARD_TIMEOUT_MSECS)
    except TimeoutError as e:
        error(get_language_string("core-error-no-points-cards") % e)
        if close and not page.is_closed():
            await page.close()
        return True
    for i in range(await cards.count()):
        card = cards.nth(i)
        title = (await card.locator(
            PointsSelectors.CARD_TITLE).first.inner_text()).strip()
        if title in _config.skipped:
            if not set_task_status_by_task_title(title, TaskStatus.SKIPPED):
                warning(get_language_string(
                    "core-warning-failed-to-skip-task") % title)
        elif not await _is_card_finished(card):
            if (title not in tasks_to_be_done):
                tasks_to_be_done.append(title)
    find_event_by_id(EventID.SCORE_UPDATED).invoke(tuple(scores))

    if close and not page.is_closed():
        await page.close()
    return len(tasks_to_be_done) == 0


async def _finish_video_task(
    playwright: Playwright,
    main_context: BrowserContext,
    task_title: str,
    close: bool,
) -> bool:
    """Retry a video task in a short-lived headed context."""
    video_browser = None
    video_context = None
    try:
        video_browser = await playwright[_config.browser_id].launch(
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
        video_context = await video_browser.new_context(
            storage_state=await main_context.storage_state(),
        )
        await restore_session_storage_async(video_context)
        video_context.set_default_timeout(WAIT_PAGE_SECS * 1000)
        info("视频详情页无头读取失败，正在使用临时有头浏览器重试")
        result = await do_task(await video_context.new_page(), task_title, close)
        try:
            await main_context.add_cookies(await video_context.cookies())
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
                    await page.close()
            await video_context.close()
        if video_browser is not None:
            await video_browser.close()


async def _finish_queue(
    queue: TaskQueue,
    context: BrowserContext,
    playwright: Playwright,
    close: bool,
):
    debug(get_language_string("core-debug-current-queue") %
          ", ".join([str(task) for task in queue]))
    results: list[bool] = []
    for task in queue:
        await wait_for_processing_resume_async()
        if task in _VIDEO_TASK_TITLES:
            task_result = await do_task(await context.new_page(), task, close)
            if not task_result:
                warning("无头视频详情页读取失败，回退到临时有头浏览器")
                task_result = await _finish_video_task(
                    playwright, context, task, close,
                )
        else:
            task_result = await do_task(await context.new_page(), task, close)
        debug(get_language_string("core-debug-task-result") %
              (str(task), str(task_result)))
        results.append(task_result)
    if not all(results):
        warning(get_language_string("core-warning-some-tasks-failed"))


async def _finish_all(
    context: BrowserContext,
    playwright: Playwright,
    close: bool = True,
):
    await wait_for_processing_resume_async()
    await do_task(await context.new_page(), "登录", close)
    while True:
        await wait_for_processing_resume_async()
        if await _get_status_from_page(await context.new_page(), close):
            break
        debug(get_language_string("core-debug-task-to-be-done-is") %
              str(tasks_to_be_done))
        queues = create_queues_from_existing_task_titles(*tasks_to_be_done)
        tasks: list[Task[None]] = []
        async with TaskGroup() as tg:
            for queue in queues:
                tasks.append(tg.create_task(
                    _finish_queue(queue, context, playwright, close)))

    if close:
        for page in context.pages:
            if not page.is_closed():
                await page.close()


async def _start():
    start_time = time()
    async with async_playwright() as p:
        browser = await p[_config.browser_id].launch(
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
            context = await browser.new_context(
                storage_state=cookies_path, **context_options)
        else:
            context = await browser.new_context(**context_options)
        if _config.browser_id == "chromium":
            await context.add_init_script(
                script=HEADLESS_BROWSER_COMPATIBILITY_SCRIPT)
        await restore_session_storage_async(context)
        context.set_default_timeout(WAIT_PAGE_SECS*1000)
        try:
            await _finish_all(context, p)
        except Exception as e:
            error(get_language_string("core-err-process-exception") % e)
        finally:
            await save_context_storage_state_async(context)
            await context.close()
            await browser.close()
    delta_mins, delta_secs = divmod(time()-start_time, 60)
    delta_hrs, delta_mins = divmod(delta_mins, 60)
    finish_str = get_language_string("core-info-all-finished").format(
        int(delta_hrs), int(delta_mins), int(delta_secs))
    info(finish_str)
    find_event_by_id(EventID.FINISHED).invoke(finish_str)


def start(): run(_start())
