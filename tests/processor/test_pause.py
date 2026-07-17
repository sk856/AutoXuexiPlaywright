"""Tests for processor pause controls."""

import pytest
from asyncio import sleep as _sleep
from asyncio import create_task as _create_task
from autoxuexiplaywright.processor.pause import resume_processing
from autoxuexiplaywright.processor.pause import is_processing_paused
from autoxuexiplaywright.processor.pause import reset_processing_pause
from autoxuexiplaywright.processor.pause import request_processing_pause
from autoxuexiplaywright.processor.pause import wait_for_processing_resume


def test_pause_state_transitions() -> None:
    """Pause and resume should update the shared state."""
    reset_processing_pause()
    assert not is_processing_paused()  # noqa: S101

    request_processing_pause()
    assert is_processing_paused()  # noqa: S101

    resume_processing()
    assert not is_processing_paused()  # noqa: S101


@pytest.mark.asyncio
async def test_async_wait_stays_blocked_until_resume() -> None:
    """The async pause gate should release only after resume."""
    request_processing_pause()
    waiter = _create_task(wait_for_processing_resume())
    await _sleep(0)
    assert not waiter.done()  # noqa: S101

    resume_processing()
    await waiter
    assert waiter.done()  # noqa: S101
