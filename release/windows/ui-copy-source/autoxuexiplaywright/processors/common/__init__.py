from enum import Enum
from re import compile
from abc import ABC, abstractmethod
from asyncio import sleep as async_sleep
from threading import Event


class TaskStatus(Enum):
    UNKNOWN = 0
    READY = 1
    SUCCESS = 2
    FAILED = 3
    SKIPPED = 4


class AbstractBaseTask(ABC):
    status = TaskStatus.UNKNOWN

    @property
    @abstractmethod
    def requires(self) -> list[str]:
        return []

    @property
    @abstractmethod
    def handles(self) -> list[str]:
        return []


WAIT_PAGE_SECS = 300
RETRY_TIMES = 3
CHECK_ELEMENT_TIMEOUT_SECS = 5
WAIT_RESULT_SECS = CHECK_ELEMENT_TIMEOUT_SECS
WAIT_CHOICE_SECS = CHECK_ELEMENT_TIMEOUT_SECS
ANSWER_SLEEP_MIN_SECS = 2.0
ANSWER_SLEEP_MAX_SECS = 5.0
READ_TIME_SECS = 60
READ_SLEEPS_MIN_SECS = 2.0
READ_SLEEPS_MAX_SECS = 5.0

VIDEO_REQUEST_REGEX = compile('https://.+.(m3u8|mp4)')

ANSWER_CONNECTOR = "#"

cache: set[str] = set()
tasks_to_be_done: list[str] = []
scores: list[int] = [-1, -1]

TaskQueue = list[str]

# A cooperative pause gate shared by the GUI tray controls and both processor
# implementations. The event is set while processing is allowed to continue.
_processing_resume_event = Event()
_processing_resume_event.set()


def reset_processing_pause() -> None:
    """Clear a previous pause request before a new run starts."""
    _processing_resume_event.set()


def request_processing_pause() -> None:
    """Request a pause at the next task/browser operation boundary."""
    _processing_resume_event.clear()


def resume_processing() -> None:
    """Resume processing after a tray pause."""
    _processing_resume_event.set()


def is_processing_paused() -> bool:
    return not _processing_resume_event.is_set()


def wait_for_processing_resume() -> None:
    """Block a synchronous processor until the pause request is released."""
    _processing_resume_event.wait()


async def wait_for_processing_resume_async() -> None:
    """Yield while an asynchronous processor is paused."""
    while is_processing_paused():
        await async_sleep(0.2)


_known_tasks: list[AbstractBaseTask] = []


def _is_task_registered(task_type: type[AbstractBaseTask]) -> bool:
    for task in _known_tasks:
        if isinstance(task, task_type):
            return True
    return False


def get_task_by_task_title(task_title: str) -> AbstractBaseTask | None:
    """Get task by task title

    Args:
        task_title (str): The title of task on status page

    Returns:
        AbstractBaseTask | None: The task instance or None if not found
    """
    for task in _known_tasks:
        if task_title in task.handles:
            return task


def register_tasks(*tasks: type[AbstractBaseTask]) -> bool:
    """Register all tasks given

    This will make them available

    Returns:
        bool: If all tasks are registered successfully
    """
    results: list[bool] = []
    for task in tasks:
        if _is_task_registered(task):
            results.append(False)
        else:
            _known_tasks.append(task())
            results.append(True)
    return all(results)


def clean_tasks():
    """Remove all the registered tasks
    """
    _known_tasks.clear()


def set_task_status_by_task_title(task_title: str, status: TaskStatus) -> bool:
    """Set task status by task title

    Args:
        task_title (str): The title of task on status page
        status (TaskStatus): The status you want to set

    Returns:
        bool: If set successfully
    """
    task = get_task_by_task_title(task_title)
    if task != None:
        task.status = status
        return True
    return False


def create_queues_from_existing_task_titles(*task_titles: str) -> list[TaskQueue]:
    """Create task queue from titles

    Args:
        *task_titles (str): The list of task title

    Returns:
        list[TaskQueue]: The queues ordered by requires
    """
    queues_dict: dict[int, TaskQueue] = {}
    for task_title in task_titles:
        task = get_task_by_task_title(task_title)
        if task != None:
            requires_count = len(task.requires)
            if requires_count in queues_dict.keys():
                queues_dict[requires_count].append(task_title)
            else:
                queues_dict[requires_count] = [task_title]
    keys = list(queues_dict.keys())
    keys.sort()
    return list({key: queues_dict[key] for key in keys}.values())


def clean_string(string: str) -> str:
    """Clean the string

    Args:
        string (str): The input string

    Returns:
        str The new string which is stripped and replaced newline with space
    """
    return string.strip().replace("\n", "")
