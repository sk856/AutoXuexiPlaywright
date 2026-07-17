"""Thread-safe pause controls shared by the processor and GUI."""

from asyncio import to_thread as _to_thread
from threading import Event as _Event


_resume_event = _Event()
_resume_event.set()


def reset_processing_pause() -> None:
    """Clear a previous pause request before starting a processor run."""
    _resume_event.set()


def request_processing_pause() -> None:
    """Request a pause at the next task boundary."""
    _resume_event.clear()


def resume_processing() -> None:
    """Release a pending pause request."""
    _resume_event.set()


def is_processing_paused() -> bool:
    """Return whether the processor is currently paused or pause-requested."""
    return not _resume_event.is_set()


def wait_for_processing_resume_sync() -> None:
    """Block a synchronous caller until processing is resumed."""
    _resume_event.wait()


async def wait_for_processing_resume() -> None:
    """Yield to the asyncio loop until processing is resumed."""
    if not _resume_event.is_set():
        await _to_thread(_resume_event.wait)
