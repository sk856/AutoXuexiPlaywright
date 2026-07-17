"""Test drag captcha element selection."""

from asyncio import run as _run
from autoxuexiplaywright.processor.captcha_handlers.drag import _first_visible


class _FakeCandidate:
    """Represent a candidate locator with a fixed visibility state."""

    def __init__(self, visible: bool) -> None:
        self.visible = visible

    async def is_visible(self) -> bool:
        """Return the configured visibility state."""
        return self.visible


class _FakeCandidates:
    """Provide the locator collection methods used by the selector helper."""

    def __init__(self, *candidates: _FakeCandidate) -> None:
        self.candidates = candidates

    async def count(self) -> int:
        """Return the number of candidate locators."""
        return len(self.candidates)

    def nth(self, index: int) -> _FakeCandidate:
        """Return the candidate at the requested index."""
        return self.candidates[index]


def test_first_visible_skips_hidden_candidates() -> None:
    """A hidden template should not mask a later visible captcha element."""
    hidden = _FakeCandidate(visible=False)
    visible = _FakeCandidate(visible=True)

    result = _run(_first_visible(_FakeCandidates(hidden, visible)))  # type: ignore[arg-type]

    assert result is visible  # noqa: S101


def test_first_visible_returns_none_when_all_candidates_are_hidden() -> None:
    """The helper should report no match when every candidate is hidden."""
    candidates = _FakeCandidates(
        _FakeCandidate(visible=False),
        _FakeCandidate(visible=False),
    )

    result = _run(_first_visible(candidates))  # type: ignore[arg-type]

    assert result is None  # noqa: S101
