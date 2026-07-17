"""Tests for OpenAI-compatible endpoint normalization."""

import pytest
from autoxuexiplaywright.processor.answer_sources.openai_compatible import _models_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com", "https://example.com/v1/models"),
        ("https://example.com/", "https://example.com/v1/models"),
        ("https://example.com/v1", "https://example.com/v1/models"),
        ("https://example.com/models", "https://example.com/models"),
        ("https://example.com/v1/models", "https://example.com/v1/models"),
        (
            "https://example.com/v1/chat/completions",
            "https://example.com/v1/models",
        ),
    ],
)
def test_models_url(url: str, expected: str) -> None:
    """Accept base URLs as well as explicit model-list endpoints."""
    assert _models_url(url) == expected  # noqa: S101
